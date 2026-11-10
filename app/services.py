"""Service layer: every business rule lives here.
Routers call services; services call repositories and own the transaction."""
import uuid
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import schemas
from .models import (Application, ApplicationStatus as S, Branch, Company, InterviewSlot,
                     JobAllowedBranch, JobListing, Offer, Student)
from .repositories import (ApplicationRepository, CompanyRepository, InterviewRepository,
                           JobRepository, OfferRepository, StatsRepository, UserRepository)
from .security import create_token, hash_password, verify_password


# ---------------------------------------------------------------- errors
class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Unauthorized(DomainError):
    status_code = 401


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Ineligible(DomainError):
    status_code = 422


def _commit(db: Session, conflict_message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict(conflict_message)


# ---------------------------------------------------------------- auth
_DUMMY_HASH = hash_password("not-a-real-password")


def login(db: Session, role: str, identifier: str, password: str) -> dict:
    users = UserRepository(db)
    user = users.student_by_login(identifier) if role == "student" else users.officer_by_email(identifier)
    ok = verify_password(password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        raise Unauthorized("Incorrect ID or password")
    return {"token": create_token(user.id, role),
            "user": {"id": user.id, "role": role, "name": user.full_name}}


# ---------------------------------------------------------------- eligibility
def eligibility_reason(student: Student, job: JobListing):
    """Return None if the student may apply, otherwise a short reason.
    Rules: drive open, no accepted offer, CGPA >= min, active backlogs <= max,
    branch allowed (a job with no allowed branches is open to every branch)."""
    if not job.is_open:
        return "Applications for this drive are closed"
    if student.has_accepted_offer:
        return "You have already accepted an offer"
    if student.cgpa < job.min_cgpa:
        return f"Requires a CGPA of {job.min_cgpa:g} or above"
    if student.active_backlogs > job.max_backlogs:
        n = job.max_backlogs
        return f"Allows at most {n} active backlog{'' if n == 1 else 's'}"
    branches = job.branches
    if branches and student.branch.value not in branches:
        return f"Open to {', '.join(branches)} only"
    return None


# ---------------------------------------------------------------- companies and jobs
def list_companies(db: Session) -> List[Company]:
    return CompanyRepository(db).all()


def create_company(db: Session, data: schemas.CompanyIn) -> Company:
    repo = CompanyRepository(db)
    if repo.by_name(data.name):
        raise Conflict("A company with this name already exists")
    company = repo.add(Company(name=data.name, email=data.email))
    db.commit()
    return company


def _job_out(job: JobListing, **extra) -> schemas.JobOut:
    out = schemas.JobOut.model_validate(job)
    for key, value in extra.items():
        setattr(out, key, value)
    return out


def jobs_for_student(db: Session, student: Student) -> List[schemas.JobOut]:
    applied = ApplicationRepository(db).applied_job_ids(student.id)
    return [_job_out(j, reason=eligibility_reason(student, j), applied=j.id in applied)
            for j in JobRepository(db).all()]


def jobs_for_officer(db: Session) -> List[schemas.JobOut]:
    repo = JobRepository(db)
    counts = repo.applicant_counts()
    return [_job_out(j, applicants=counts.get(j.id, 0)) for j in repo.all()]


def create_job(db: Session, data: schemas.JobIn) -> schemas.JobOut:
    if not CompanyRepository(db).get(data.company_id):
        raise NotFound("Company not found")
    job = JobListing(company_id=data.company_id, role=data.role, season=data.season,
                     min_cgpa=data.min_cgpa, max_backlogs=data.max_backlogs,
                     drive_date=data.drive_date, is_open=data.is_open)
    job.allowed_branches = [JobAllowedBranch(branch=b) for b in dict.fromkeys(data.branches)]
    JobRepository(db).add(job)
    db.commit()
    db.refresh(job)
    return _job_out(job, applicants=0)


def set_job_open(db: Session, job_id: int, is_open: bool) -> schemas.JobOut:
    job = JobRepository(db).get(job_id)
    if not job:
        raise NotFound("Drive not found")
    job.is_open = is_open
    db.commit()
    return _job_out(job, applicants=len(job.applications))


def applicants_for_job(db: Session, job_id: int) -> List[Application]:
    if not JobRepository(db).get(job_id):
        raise NotFound("Drive not found")
    return ApplicationRepository(db).for_job(job_id)


# ---------------------------------------------------------------- applications
def apply(db: Session, student: Student, job_id: int) -> Application:
    job = JobRepository(db).get(job_id)
    if not job:
        raise NotFound("Drive not found")
    apps = ApplicationRepository(db)
    if apps.find(student.id, job.id):
        raise Conflict("You have already applied to this drive")
    reason = eligibility_reason(student, job)
    if reason:
        raise Ineligible(reason)
    application = apps.add(Application(student_id=student.id, job_id=job.id, status=S.APPLIED))
    _commit(db, "You have already applied to this drive")
    return application


def applications_for_student(db: Session, student: Student) -> List[Application]:
    return ApplicationRepository(db).for_student(student.id)


def _get_application(db: Session, application_id: int) -> Application:
    application = ApplicationRepository(db).get(application_id)
    if not application:
        raise NotFound("Application not found")
    return application


def set_status(db: Session, application_id: int, status: str) -> Application:
    application = _get_application(db, application_id)
    if status == "SHORTLISTED":
        if application.status != S.APPLIED:
            raise Conflict("Only applicants who are still in the Applied stage can be shortlisted")
        application.status = S.SHORTLISTED
    else:
        if application.status not in (S.APPLIED, S.SHORTLISTED):
            raise Conflict("This application can no longer be rejected")
        application.status = S.REJECTED
    db.commit()
    return application


# ---------------------------------------------------------------- interviews
def schedule_interview(db: Session, application_id: int, data: schemas.InterviewIn) -> InterviewSlot:
    application = _get_application(db, application_id)
    if application.status != S.SHORTLISTED:
        raise Conflict("Interviews can only be scheduled for shortlisted students")
    if any(i.round_no == data.round_no for i in application.interviews):
        raise Conflict(f"Round {data.round_no} is already scheduled for this application")
    slot = InterviewRepository(db).add(InterviewSlot(
        application_id=application.id, round_no=data.round_no,
        scheduled_at=data.scheduled_at, venue=data.venue))
    _commit(db, f"Round {data.round_no} is already scheduled for this application")
    return slot


def record_interview_result(db: Session, interview_id: int, data: schemas.InterviewResultIn) -> InterviewSlot:
    slot = InterviewRepository(db).get(interview_id)
    if not slot:
        raise NotFound("Interview not found")
    if slot.application.status != S.SHORTLISTED:
        raise Conflict("Results can only be recorded while the student is shortlisted")
    slot.passed = data.passed
    slot.notes = data.notes
    db.commit()
    return slot


# ---------------------------------------------------------------- offers
def issue_offer(db: Session, application_id: int, package_lpa: float) -> Offer:
    application = _get_application(db, application_id)
    if application.status != S.SHORTLISTED:
        raise Conflict("Offers can only be issued to shortlisted students")
    allowed_branches = application.job.branches
    if allowed_branches and application.student.branch.value not in allowed_branches:
        raise Ineligible(f"This offer is restricted to {', '.join(allowed_branches)}; the student belongs to {application.student.branch.value}")
    if application.student.cgpa < application.job.min_cgpa:
        raise Ineligible(f"The student does not meet the minimum CGPA of {application.job.min_cgpa:g}")
    if application.student.active_backlogs > application.job.max_backlogs:
        raise Ineligible(f"The drive allows at most {application.job.max_backlogs} active backlogs")
    if application.student.has_accepted_offer:
        raise Conflict("This student has already accepted another offer")
    offer = OfferRepository(db).add(Offer(
        application_id=application.id, package_lpa=package_lpa,
        offer_letter_key=f"offer-{application.id}-{uuid.uuid4().hex[:8]}.pdf"))
    application.status = S.OFFERED
    _commit(db, "An offer already exists for this application")
    return offer


def accept_offer(db: Session, student: Student, offer_id: int) -> Offer:
    """Updates the offer, the application status and students.has_accepted_offer
    in ONE transaction (3NF Step 8: the duplicated facts must never disagree)."""
    offer = OfferRepository(db).get(offer_id)
    if not offer or offer.application.student_id != student.id:
        raise NotFound("Offer not found")
    if offer.accepted:
        raise Conflict("You have already accepted this offer")
    if student.has_accepted_offer:
        raise Conflict("You have already accepted another offer")
    if offer.application.status != S.OFFERED:
        raise Conflict("This offer can no longer be accepted")
    offer.accepted = True
    offer.application.status = S.ACCEPTED
    student.has_accepted_offer = True
    db.commit()
    return offer


# ---------------------------------------------------------------- reports
def placement_stats(db: Session) -> schemas.StatsOut:
    repo = StatsRepository(db)
    t = repo.totals()
    rate = round(100 * t["placed"] / t["students"], 1) if t["students"] else 0.0
    return schemas.StatsOut(
        students=t["students"], applications=t["applications"], offers=t["offers"], placed=t["placed"],
        placement_rate=rate,
        highest_package=round(t["highest"], 2) if t["highest"] is not None else None,
        average_package=round(t["average"], 2) if t["average"] is not None else None,
        by_branch=[schemas.BranchStat(**row) for row in repo.by_branch()])

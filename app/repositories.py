"""Repository layer: the only place that talks to the database.
Repositories add and query rows; services decide when to commit."""
from typing import Dict, List, Optional, Set

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.orm import Session, joinedload

from .models import (Application, Branch, Company, InterviewSlot, JobListing, Offer,
                     PlacementOfficer, Student)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def student_by_login(self, identifier: str) -> Optional[Student]:
        ident = identifier.strip()
        return self.db.scalar(select(Student).where(
            or_(Student.usn == ident.upper(), func.lower(Student.email) == ident.lower())))

    def officer_by_email(self, email: str) -> Optional[PlacementOfficer]:
        return self.db.scalar(select(PlacementOfficer).where(
            func.lower(PlacementOfficer.email) == email.strip().lower()))


class CompanyRepository:
    def __init__(self, db: Session):
        self.db = db

    def all(self) -> List[Company]:
        return list(self.db.scalars(select(Company).order_by(Company.name)))

    def get(self, company_id: int) -> Optional[Company]:
        return self.db.get(Company, company_id)

    def by_name(self, name: str) -> Optional[Company]:
        return self.db.scalar(select(Company).where(func.lower(Company.name) == name.lower()))

    def add(self, company: Company) -> Company:
        self.db.add(company)
        self.db.flush()
        return company


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def all(self) -> List[JobListing]:
        stmt = (select(JobListing).options(joinedload(JobListing.company))
                .order_by(JobListing.drive_date, JobListing.id))
        return list(self.db.scalars(stmt).unique())

    def get(self, job_id: int) -> Optional[JobListing]:
        return self.db.get(JobListing, job_id)

    def add(self, job: JobListing) -> JobListing:
        self.db.add(job)
        self.db.flush()
        return job

    def applicant_counts(self) -> Dict[int, int]:
        rows = self.db.execute(select(Application.job_id, func.count()).group_by(Application.job_id))
        return {job_id: n for job_id, n in rows}


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, application_id: int) -> Optional[Application]:
        return self.db.get(Application, application_id)

    def find(self, student_id: int, job_id: int) -> Optional[Application]:
        return self.db.scalar(select(Application).where(
            Application.student_id == student_id, Application.job_id == job_id))

    def applied_job_ids(self, student_id: int) -> Set[int]:
        return set(self.db.scalars(select(Application.job_id).where(Application.student_id == student_id)))

    def for_student(self, student_id: int) -> List[Application]:
        stmt = (select(Application).where(Application.student_id == student_id)
                .options(joinedload(Application.job).joinedload(JobListing.company))
                .order_by(Application.applied_at.desc(), Application.id.desc()))
        return list(self.db.scalars(stmt).unique())

    def for_job(self, job_id: int) -> List[Application]:
        stmt = (select(Application).where(Application.job_id == job_id)
                .options(joinedload(Application.student))
                .order_by(Application.applied_at, Application.id))
        return list(self.db.scalars(stmt).unique())

    def add(self, application: Application) -> Application:
        self.db.add(application)
        self.db.flush()
        return application


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, interview_id: int) -> Optional[InterviewSlot]:
        return self.db.get(InterviewSlot, interview_id)

    def add(self, slot: InterviewSlot) -> InterviewSlot:
        self.db.add(slot)
        self.db.flush()
        return slot


class OfferRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, offer_id: int) -> Optional[Offer]:
        return self.db.get(Offer, offer_id)

    def add(self, offer: Offer) -> Offer:
        self.db.add(offer)
        self.db.flush()
        return offer


class StatsRepository:
    def __init__(self, db: Session):
        self.db = db

    def totals(self) -> dict:
        db = self.db
        accepted = Offer.accepted.is_(True)
        return {
            "students": db.scalar(select(func.count()).select_from(Student)) or 0,
            "applications": db.scalar(select(func.count()).select_from(Application)) or 0,
            "offers": db.scalar(select(func.count()).select_from(Offer)) or 0,
            "placed": db.scalar(select(func.count()).select_from(Offer).where(accepted)) or 0,
            # Package reports track every issued offer; placement counts/rate
            # still track accepted offers only.
            "highest": db.scalar(select(func.max(Offer.package_lpa))),
            "average": db.scalar(select(func.avg(Offer.package_lpa))),
        }

    def by_branch(self) -> List[dict]:
        rows = self.db.execute(
            select(Student.branch, func.count(), func.sum(Student.has_accepted_offer.cast(Integer)))
            .group_by(Student.branch)).all()
        found = {b.value: (n, int(p or 0)) for b, n, p in rows}
        return [{"branch": b.value, "students": found.get(b.value, (0, 0))[0],
                 "placed": found.get(b.value, (0, 0))[1]} for b in Branch]


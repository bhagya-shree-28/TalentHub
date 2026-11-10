"""Demo data so the site is usable the moment it starts.
Demo logins:  student 1RV22CS101 / student123    officer placement@college.edu / officer123"""
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from .models import (Application, ApplicationStatus as S, Branch, Company, InterviewSlot,
                     JobAllowedBranch, JobListing, Offer, PlacementOfficer, Student)
from .security import hash_password


def seed(db: Session) -> bool:
    if db.query(Student).first() or db.query(PlacementOfficer).first():
        return False

    student_hash, officer_hash = hash_password("student123"), hash_password("officer123")
    today = date.today()
    day = lambda n: today + timedelta(days=n)
    at = lambda n, h, m=0: datetime.combine(day(n), time(h, m))

    db.add(PlacementOfficer(full_name="Placement Cell", email="placement@college.edu", password_hash=officer_hash))

    companies = {n: Company(name=n, email=e) for n, e in [
        ("ABC Technologies", "careers@abctech.example"), ("Infosys", "campus@infosys.example"),
        ("TCS", "campus@tcs.example"), ("Bosch", "hiring@bosch.example"),
        ("Wipro", "campus@wipro.example"), ("Larsen & Toubro", "gradhiring@lnt.example"),
        ("Cognizant", "campus@cognizant.example")]}
    db.add_all(companies.values())
    db.flush()  # insert in stages so primary keys follow the order written below

    students = {}
    for usn, name, branch, cgpa, active, cleared in [
        ("1RV22CS101", "Rahul Kumar", "CSE", 8.2, 1, 0), ("1RV22IS045", "Asha Patil", "ISE", 9.1, 0, 1),
        ("1RV22EC072", "Ravi Menon", "ECE", 7.4, 0, 0), ("1RV22CS118", "Sneha Rao", "CSE", 8.8, 0, 0),
        ("1RV22ME031", "Arjun Nair", "MECH", 6.9, 2, 1), ("1RV22CV009", "Divya Shetty", "CIVIL", 7.8, 0, 0),
        ("1RV22CS140", "Karthik Iyer", "CSE", 6.2, 3, 2), ("1RV22EC088", "Meera Joshi", "ECE", 8.5, 0, 0),
        ("1RV22IS060", "Imran Sheikh", "ISE", 7.1, 1, 0), ("1RV22ME044", "Pooja Hegde", "MECH", 8.0, 0, 0)]:
        students[usn] = Student(usn=usn, full_name=name, email=f"{name.split()[0].lower()}@college.edu",
                                branch=Branch(branch), cgpa=cgpa, active_backlogs=active,
                                cleared_backlogs=cleared, password_hash=student_hash)

    db.add_all(students.values())
    db.flush()

    def job(company, role, min_cgpa, max_backlogs, days, branches=(), is_open=True):
        j = JobListing(company=companies[company], role=role, season="2026", min_cgpa=min_cgpa,
                       max_backlogs=max_backlogs, drive_date=day(days), is_open=is_open)
        j.allowed_branches = [JobAllowedBranch(branch=Branch(b)) for b in branches]
        return j

    j1 = job("ABC Technologies", "Software Developer", 7.0, 2, 14, ["CSE", "ISE"])
    j2 = job("Infosys", "Systems Engineer", 6.5, 1, 10)
    j3 = job("TCS", "Digital Graduate", 8.5, 0, 21, ["CSE", "ISE", "ECE"])
    j4 = job("Bosch", "Embedded Engineer", 7.0, 1, 25, ["ECE", "MECH"])
    j5 = job("Wipro", "Project Engineer", 6.0, 2, -5, is_open=False)
    j6 = job("Larsen & Toubro", "Graduate Engineer Trainee", 6.5, 1, 18, ["CIVIL", "MECH"])
    j7 = job("Cognizant", "Programmer Analyst", 6.0, 2, 30)

    db.add_all([j1, j2, j3, j4, j5, j6, j7])
    db.flush()

    def app(usn, j, status, days_ago):
        when = at(-days_ago, 9)
        return Application(student=students[usn], job=j, status=status, applied_at=when, updated_at=when)

    a1 = app("1RV22CS101", j2, S.SHORTLISTED, 6)
    a2 = app("1RV22IS045", j2, S.APPLIED, 5)
    a3 = app("1RV22EC072", j2, S.APPLIED, 4)
    a4 = app("1RV22IS045", j1, S.SHORTLISTED, 8)
    a5 = app("1RV22CS118", j1, S.OFFERED, 9)
    a6 = app("1RV22EC088", j4, S.ACCEPTED, 12)
    a7 = app("1RV22CS101", j1, S.APPLIED, 2)
    a8 = app("1RV22EC072", j4, S.REJECTED, 10)
    a9 = app("1RV22CS118", j3, S.APPLIED, 1)
    students["1RV22EC088"].has_accepted_offer = True
    db.add_all([a1, a2, a3, a4, a5, a6, a7, a8, a9])
    db.flush()

    slots = [
        InterviewSlot(application=a1, round_no=1, scheduled_at=at(3, 10), venue="Seminar Hall B"),
        InterviewSlot(application=a4, round_no=1, scheduled_at=at(-2, 11), venue="Placement Cell, Room 2", passed=True,
                      notes="Strong problem solving"),
        InterviewSlot(application=a4, round_no=2, scheduled_at=at(4, 14, 30), venue="Online (Teams)"),
    ]
    offers = [
        Offer(application=a5, package_lpa=12.0, offer_letter_key="offer-seed-5.pdf", accepted=False),
        Offer(application=a6, package_lpa=7.5, offer_letter_key="offer-seed-6.pdf", accepted=True),
    ]

    db.add_all([*slots, *offers])
    db.commit()
    return True

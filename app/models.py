"""Model layer: the 7 tables of the final TalentHub schema (Part D)
plus `placement_officers` and `students.password_hash`, which login needs."""
import enum
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey,
                        Integer, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Branch(str, enum.Enum):
    CSE = "CSE"
    ISE = "ISE"
    ECE = "ECE"
    MECH = "MECH"
    CIVIL = "CIVIL"


class ApplicationStatus(str, enum.Enum):
    APPLIED = "APPLIED"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"


def _enum(cls, name):
    return Enum(cls, name=name, native_enum=False, create_constraint=True, length=20,
                values_callable=lambda e: [m.value for m in e])


def _decimal(p, s):
    return Numeric(p, s, asdecimal=False)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    usn: Mapped[str] = mapped_column(String(20), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    branch: Mapped[Branch] = mapped_column(_enum(Branch, "student_branch"))
    cgpa: Mapped[float] = mapped_column(_decimal(4, 2))
    active_backlogs: Mapped[int] = mapped_column(Integer)
    cleared_backlogs: Mapped[int] = mapped_column(Integer)
    has_accepted_offer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    password_hash: Mapped[str] = mapped_column(String(255))
    applications: Mapped[List["Application"]] = relationship(back_populates="student")

    __table_args__ = (
        CheckConstraint("cgpa >= 0 AND cgpa <= 10", name="ck_students_cgpa"),
        CheckConstraint("active_backlogs >= 0 AND cleared_backlogs >= 0", name="ck_students_backlogs"),
    )


class PlacementOfficer(Base):
    __tablename__ = "placement_officers"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160))
    jobs: Mapped[List["JobListing"]] = relationship(back_populates="company")


class JobListing(Base):
    __tablename__ = "job_listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    role: Mapped[str] = mapped_column(String(120))
    season: Mapped[str] = mapped_column(String(20))
    min_cgpa: Mapped[float] = mapped_column(_decimal(4, 2))
    max_backlogs: Mapped[int] = mapped_column(Integer)
    drive_date: Mapped[date] = mapped_column(Date)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    company: Mapped[Company] = relationship(back_populates="jobs")
    allowed_branches: Mapped[List["JobAllowedBranch"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin")
    applications: Mapped[List["Application"]] = relationship(back_populates="job")

    __table_args__ = (
        CheckConstraint("min_cgpa >= 0 AND min_cgpa <= 10", name="ck_jobs_min_cgpa"),
        CheckConstraint("max_backlogs >= 0", name="ck_jobs_max_backlogs"),
    )

    @property
    def company_name(self) -> str:
        return self.company.name

    @property
    def branches(self) -> List[str]:
        order = list(Branch)
        return [b.branch.value for b in sorted(self.allowed_branches, key=lambda x: order.index(x.branch))]


class JobAllowedBranch(Base):
    __tablename__ = "job_allowed_branches"
    job_id: Mapped[int] = mapped_column(ForeignKey("job_listings.id", ondelete="CASCADE"), primary_key=True)
    branch: Mapped[Branch] = mapped_column(_enum(Branch, "job_branch"), primary_key=True)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    job_id: Mapped[int] = mapped_column(ForeignKey("job_listings.id"))
    status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus, "application_status"), default=ApplicationStatus.APPLIED)
    applied_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    student: Mapped[Student] = relationship(back_populates="applications")
    job: Mapped[JobListing] = relationship(back_populates="applications")
    interviews: Mapped[List["InterviewSlot"]] = relationship(
        back_populates="application", order_by="InterviewSlot.round_no",
        cascade="all, delete-orphan", lazy="selectin")
    offer: Mapped[Optional["Offer"]] = relationship(
        back_populates="application", uselist=False, cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (UniqueConstraint("student_id", "job_id", name="uq_applications_student_job"),)


class InterviewSlot(Base):
    __tablename__ = "interview_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    round_no: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    venue: Mapped[str] = mapped_column(String(160))
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application: Mapped[Application] = relationship(back_populates="interviews")

    __table_args__ = (
        UniqueConstraint("application_id", "round_no", name="uq_interviews_application_round"),
        CheckConstraint("round_no >= 1", name="ck_interviews_round"),
    )


class Offer(Base):
    __tablename__ = "offers"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), unique=True)
    package_lpa: Mapped[float] = mapped_column(_decimal(8, 2))
    offer_letter_key: Mapped[str] = mapped_column(String(120))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    application: Mapped[Application] = relationship(back_populates="offer")

    __table_args__ = (CheckConstraint("package_lpa > 0", name="ck_offers_package"),)

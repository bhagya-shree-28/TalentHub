"""Request and response shapes (Pydantic)."""
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import ApplicationStatus, Branch


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Strict(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# ---- auth ----
class LoginIn(Strict):
    role: Literal["student", "officer"]
    identifier: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    role: str
    name: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


# ---- people and companies ----
class StudentOut(ORM):
    id: int
    usn: str
    full_name: str
    email: str
    branch: Branch
    cgpa: float
    active_backlogs: int
    cleared_backlogs: int
    has_accepted_offer: bool


class CompanyIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=160)


class CompanyOut(ORM):
    id: int
    name: str
    email: str


# ---- jobs ----
class JobIn(Strict):
    company_id: int
    role: str = Field(min_length=1, max_length=120)
    season: str = Field(min_length=1, max_length=20)
    min_cgpa: float = Field(ge=0, le=10)
    max_backlogs: int = Field(ge=0, le=50)
    drive_date: date
    is_open: bool = True
    branches: List[Branch] = []


class JobPatch(BaseModel):
    is_open: bool


class JobOut(ORM):
    id: int
    company_id: int
    company: str = Field(validation_alias="company_name")
    role: str
    season: str
    min_cgpa: float
    max_backlogs: int
    drive_date: date
    is_open: bool
    branches: List[str]
    reason: Optional[str] = None      # students: why they cannot apply (null = eligible)
    applied: Optional[bool] = None    # students: already applied?
    applicants: Optional[int] = None  # officers: number of applications


class JobBrief(ORM):
    id: int
    role: str
    company: str = Field(validation_alias="company_name")
    drive_date: date


# ---- applications, interviews, offers ----
class InterviewIn(Strict):
    round_no: int = Field(ge=1, le=20)
    scheduled_at: datetime
    venue: str = Field(min_length=1, max_length=160)


class InterviewResultIn(Strict):
    passed: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class InterviewOut(ORM):
    id: int
    round_no: int
    scheduled_at: datetime
    venue: str
    passed: Optional[bool]
    notes: Optional[str]


class OfferIn(BaseModel):
    package_lpa: float = Field(gt=0, le=1000)


class OfferOut(ORM):
    id: int
    package_lpa: float
    accepted: bool
    offer_letter_key: str


class ApplyIn(BaseModel):
    job_id: int


class StatusIn(BaseModel):
    status: Literal["SHORTLISTED", "REJECTED"]


class ApplicationOut(ORM):
    id: int
    status: ApplicationStatus
    applied_at: datetime
    updated_at: datetime
    job: JobBrief
    interviews: List[InterviewOut]
    offer: Optional[OfferOut]


class ApplicantOut(ORM):
    id: int
    status: ApplicationStatus
    applied_at: datetime
    student: StudentOut
    interviews: List[InterviewOut]
    offer: Optional[OfferOut]


# ---- reports ----
class BranchStat(BaseModel):
    branch: str
    students: int
    placed: int


class StatsOut(BaseModel):
    students: int
    applications: int
    offers: int
    placed: int
    placement_rate: float
    highest_package: Optional[float]
    average_package: Optional[float]
    by_branch: List[BranchStat]

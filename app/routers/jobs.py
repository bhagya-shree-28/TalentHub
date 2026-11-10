from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db
from ..deps import current_actor, current_officer

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=List[schemas.JobOut])
def list_jobs(db: Session = Depends(get_db), actor=Depends(current_actor)):
    """Students see eligibility (`reason`, `applied`); officers see applicant counts."""
    role, user = actor
    return services.jobs_for_student(db, user) if role == "student" else services.jobs_for_officer(db)


@router.post("", response_model=schemas.JobOut, status_code=201)
def create_job(data: schemas.JobIn, db: Session = Depends(get_db), _officer=Depends(current_officer)):
    return services.create_job(db, data)


@router.patch("/{job_id}", response_model=schemas.JobOut)
def update_job(job_id: int, data: schemas.JobPatch, db: Session = Depends(get_db), _officer=Depends(current_officer)):
    return services.set_job_open(db, job_id, data.is_open)


@router.get("/{job_id}/applicants", response_model=List[schemas.ApplicantOut])
def applicants(job_id: int, db: Session = Depends(get_db), _officer=Depends(current_officer)):
    return services.applicants_for_job(db, job_id)

"""Applications, interviews and offers: the whole student journey after 'Apply'."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db
from ..deps import current_officer, current_student
from ..models import Student

router = APIRouter(prefix="/api", tags=["applications"])


@router.post("/applications", response_model=schemas.ApplicationOut, status_code=201)
def apply(data: schemas.ApplyIn, db: Session = Depends(get_db), student: Student = Depends(current_student)):
    return services.apply(db, student, data.job_id)


@router.get("/applications/me", response_model=List[schemas.ApplicationOut])
def my_applications(db: Session = Depends(get_db), student: Student = Depends(current_student)):
    return services.applications_for_student(db, student)


@router.patch("/applications/{application_id}", response_model=schemas.ApplicantOut)
def update_status(application_id: int, data: schemas.StatusIn, db: Session = Depends(get_db),
                  _officer=Depends(current_officer)):
    return services.set_status(db, application_id, data.status)


@router.post("/applications/{application_id}/interviews", response_model=schemas.InterviewOut, status_code=201)
def schedule_interview(application_id: int, data: schemas.InterviewIn, db: Session = Depends(get_db),
                       _officer=Depends(current_officer)):
    return services.schedule_interview(db, application_id, data)


@router.patch("/interviews/{interview_id}", response_model=schemas.InterviewOut)
def record_result(interview_id: int, data: schemas.InterviewResultIn, db: Session = Depends(get_db),
                  _officer=Depends(current_officer)):
    return services.record_interview_result(db, interview_id, data)


@router.post("/applications/{application_id}/offer", response_model=schemas.OfferOut, status_code=201)
def issue_offer(application_id: int, data: schemas.OfferIn, db: Session = Depends(get_db),
                _officer=Depends(current_officer)):
    return services.issue_offer(db, application_id, data.package_lpa)


@router.post("/offers/{offer_id}/accept", response_model=schemas.OfferOut)
def accept_offer(offer_id: int, db: Session = Depends(get_db), student: Student = Depends(current_student)):
    return services.accept_offer(db, student, offer_id)

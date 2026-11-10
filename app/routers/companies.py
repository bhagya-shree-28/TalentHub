from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db
from ..deps import current_actor, current_officer

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("", response_model=List[schemas.CompanyOut])
def list_companies(db: Session = Depends(get_db), _actor=Depends(current_actor)):
    return services.list_companies(db)


@router.post("", response_model=schemas.CompanyOut, status_code=201)
def create_company(data: schemas.CompanyIn, db: Session = Depends(get_db), _officer=Depends(current_officer)):
    return services.create_company(db, data)

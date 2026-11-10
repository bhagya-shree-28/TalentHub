from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db
from ..deps import current_officer

router = APIRouter(prefix="/api/stats", tags=["reports"])


@router.get("", response_model=schemas.StatsOut)
def stats(db: Session = Depends(get_db), _officer=Depends(current_officer)):
    return services.placement_stats(db)

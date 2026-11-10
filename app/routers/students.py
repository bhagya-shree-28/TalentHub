from fastapi import APIRouter, Depends

from .. import schemas
from ..deps import current_student
from ..models import Student

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/me", response_model=schemas.StudentOut)
def my_profile(student: Student = Depends(current_student)):
    return student

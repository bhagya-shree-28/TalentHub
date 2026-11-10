"""Authentication dependencies shared by the routers."""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import PlacementOfficer, Student
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def _claims(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    if not creds:
        raise HTTPException(401, "Please sign in to continue")
    try:
        return decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has expired. Please sign in again.")


def current_actor(claims: dict = Depends(_claims), db: Session = Depends(get_db)):
    """Returns (role, user) for whoever is signed in."""
    role = claims.get("role")
    model = {"student": Student, "officer": PlacementOfficer}.get(role)
    try:
        user = db.get(model, int(claims["sub"])) if model else None
    except (KeyError, ValueError):
        user = None
    if user is None:
        raise HTTPException(401, "Account not found. Please sign in again.")
    return role, user


def current_student(actor=Depends(current_actor)) -> Student:
    if actor[0] != "student":
        raise HTTPException(403, "This action is only available to students")
    return actor[1]


def current_officer(actor=Depends(current_actor)) -> PlacementOfficer:
    if actor[0] != "officer":
        raise HTTPException(403, "This action is only available to placement officers")
    return actor[1]

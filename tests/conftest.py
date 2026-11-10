import os
import tempfile

# Use a throwaway database file; this must be set before the app is imported.
_tmp = tempfile.mkdtemp()
os.environ["TALENTHUB_DB_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["TALENTHUB_SEED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.seed import seed


@pytest.fixture()
def client():
    """A fresh, seeded database for every test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    with TestClient(app) as c:
        yield c


def _login(client, role, identifier, password):
    r = client.post("/api/auth/login", json={"role": role, "identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture()
def rahul(client):      # CSE, CGPA 8.2, 1 active backlog
    return _login(client, "student", "1RV22CS101", "student123")


@pytest.fixture()
def officer(client):
    return _login(client, "officer", "placement@college.edu", "officer123")


@pytest.fixture()
def login(client):
    return lambda usn: _login(client, "student", usn, "student123")

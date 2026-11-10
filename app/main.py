"""TalentHub: FastAPI entry point. Serves the JSON API under /api and the website at /."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (registers the tables)
from .config import SEED_DEMO_DATA, STATIC_DIR
from .database import Base, SessionLocal, engine
from .routers import applications, auth, companies, jobs, stats, students
from .seed import seed
from .services import DomainError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if SEED_DEMO_DATA:
        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="TalentHub API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body")
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return JSONResponse({"detail": "; ".join(parts) or "Invalid request"}, status_code=422)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


for module in (auth, students, companies, jobs, applications, stats):
    app.include_router(module.router)

# The website. Mounted last so it never shadows an /api route.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")

"""Application settings. Override any of these with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

DATABASE_URL = os.getenv("TALENTHUB_DB_URL", f"sqlite:///{BASE_DIR / 'talenthub.db'}")
# Change this in any real deployment: export TALENTHUB_SECRET="a-long-random-string"
SECRET_KEY = os.getenv("TALENTHUB_SECRET", "dev-only-secret-change-me-before-deploying-0123456789")
TOKEN_HOURS = int(os.getenv("TALENTHUB_TOKEN_HOURS", "8"))
SEED_DEMO_DATA = os.getenv("TALENTHUB_SEED", "1") == "1"

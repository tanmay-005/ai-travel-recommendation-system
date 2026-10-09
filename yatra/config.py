"""App settings in one place."""
import os
import secrets
import warnings
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent   # project root (folder that holds run.py)

load_dotenv(BASE_DIR / ".env")   # copies the lines in .env into os.environ


def _secret_key():
    key = os.environ.get("SECRET_KEY")
    if not key:
        warnings.warn("SECRET_KEY not set in .env - using a random key, so logins reset on every restart.")
        key = secrets.token_hex(32)
    return key


class Config:
    SECRET_KEY = _secret_key()
    DB_PATH = BASE_DIR / "yatra.db"
    PLACES_CSV = BASE_DIR / "data" / "places.csv"
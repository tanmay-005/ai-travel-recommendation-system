"""App settings in one place."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # project root (folder that holds run.py)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    DB_PATH = BASE_DIR / "yatra.db"
    PLACES_CSV = BASE_DIR / "india_places_dataset.csv"
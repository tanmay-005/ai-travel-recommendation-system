"""SQLite connection and table setup."""
import sqlite3

from flask import current_app

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT    UNIQUE NOT NULL,
        email       TEXT    UNIQUE NOT NULL,
        password    TEXT    NOT NULL,
        created_at  TEXT,
        last_login  TEXT
    );

    CREATE TABLE IF NOT EXISTS saved_places (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        place       TEXT    NOT NULL,
        city        TEXT,
        category    TEXT,
        lat         REAL,
        lon         REAL,
        icon        TEXT,
        saved_at    TEXT,
        UNIQUE(user_id, place)
    );
    """)
    conn.commit()
    conn.close()
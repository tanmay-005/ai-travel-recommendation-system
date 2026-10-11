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

    -- My Bag: one row per place a user has saved. Replaces the old saved_places table.
    DROP TABLE IF EXISTS saved_places;
    CREATE TABLE IF NOT EXISTS bag_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES users(id),
        osm_id      TEXT    NOT NULL,          -- e.g. "w175844355": the same id as in places.csv
        place       TEXT    NOT NULL,
        destination TEXT,                      -- what they were exploring, e.g. "Hampi"
        label       TEXT,                      -- e.g. "Trek", "Waterfall"
        lat         REAL    NOT NULL,
        lon         REAL    NOT NULL,
        saved_at    TEXT,
        UNIQUE(user_id, osm_id)                -- saving twice keeps one row
    );
    """)
    conn.commit()
    conn.close()
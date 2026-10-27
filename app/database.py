"""SQLite connection handling and schema creation.

Uses the standard-library sqlite3 module with parameterised queries only.
The database path can be overridden with the STUDENTS_DB_PATH env variable
(the tests use this to get an isolated database).
"""
import os
import sqlite3
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "students.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    date_of_birth   TEXT    NOT NULL,           -- ISO format YYYY-MM-DD
    email           TEXT    UNIQUE,
    phone           TEXT,
    course          TEXT,
    address         TEXT,
    enrollment_date TEXT,                       -- ISO format YYYY-MM-DD
    CHECK (email IS NOT NULL OR phone IS NOT NULL)
);
"""


def get_db_path() -> str:
    return os.environ.get("STUDENTS_DB_PATH", str(DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def get_conn() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()

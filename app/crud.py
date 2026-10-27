"""Database access functions. All SQL is static and parameterised."""
import sqlite3
from datetime import date
from typing import Optional

UPDATABLE = ("name", "date_of_birth", "email", "phone", "course", "address", "enrollment_date")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _serialise(data: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}


def create_student(conn: sqlite3.Connection, data: dict) -> dict:
    data = _serialise(data)
    cols = ("name", "date_of_birth", "email", "phone", "course", "address", "enrollment_date")
    values = [data.get(c) for c in cols]
    cur = conn.execute(
        "INSERT INTO students (name, date_of_birth, email, phone, course, address, enrollment_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        values,
    )
    conn.commit()
    return get_student(conn, cur.lastrowid)


def get_student(conn: sqlite3.Connection, student_id: int) -> Optional[dict]:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_students(
    conn: sqlite3.Connection,
    name: Optional[str] = None,
    course: Optional[str] = None,
    email: Optional[str] = None,
    born_after: Optional[date] = None,
    born_before: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    # The WHERE clause is assembled from fixed fragments; every value is a bound parameter.
    clauses, params = [], []
    if name:
        clauses.append("name LIKE ? COLLATE NOCASE")
        params.append(f"%{name}%")
    if course:
        clauses.append("course LIKE ? COLLATE NOCASE")
        params.append(f"%{course}%")
    if email:
        clauses.append("email = ? COLLATE NOCASE")
        params.append(email)
    if born_after:
        clauses.append("date_of_birth > ?")
        params.append(born_after.isoformat())
    if born_before:
        clauses.append("date_of_birth < ?")
        params.append(born_before.isoformat())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM students {where} ORDER BY id LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_students(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]


def update_student(conn: sqlite3.Connection, student_id: int, changes: dict) -> Optional[dict]:
    changes = _serialise({k: v for k, v in changes.items() if k in UPDATABLE})
    if get_student(conn, student_id) is None:
        return None
    if changes:
        # column names come from the UPDATABLE whitelist, never from user input
        assignments = ", ".join(f"{col} = ?" for col in changes)
        conn.execute(
            f"UPDATE students SET {assignments} WHERE id = ?",
            (*changes.values(), student_id),
        )
        conn.commit()
    return get_student(conn, student_id)


def delete_student(conn: sqlite3.Connection, student_id: int) -> bool:
    cur = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    return cur.rowcount > 0

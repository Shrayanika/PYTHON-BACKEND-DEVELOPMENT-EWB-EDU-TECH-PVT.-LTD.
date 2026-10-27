"""FastAPI application: Students Database CRUD (+ optional Ollama question answering)."""
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status

from . import ai, crud
from .database import get_conn, init_db
from .schemas import AskRequest, AskResponse, StudentCreate, StudentOut, StudentUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Students Database API",
    description="CRUD API for student records (FastAPI + SQLite) with an optional local-AI endpoint (Ollama).",
    version="1.0.0",
    lifespan=lifespan,
)


def _not_found(student_id: int) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student {student_id} not found")


@app.get("/", tags=["health"])
def root():
    return {"message": "Students API is running", "docs": "/docs"}


# ---------- Create ----------
@app.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED, tags=["students"])
def create_student(payload: StudentCreate, conn: sqlite3.Connection = Depends(get_conn)):
    try:
        return crud.create_student(conn, payload.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A student with this email already exists")


# ---------- Read ----------
@app.get("/students", response_model=list[StudentOut], tags=["students"])
def list_students(
    name: Optional[str] = Query(None, description="Case-insensitive partial match"),
    course: Optional[str] = Query(None, description="Case-insensitive partial match"),
    email: Optional[str] = Query(None, description="Exact match (case-insensitive)"),
    born_after: Optional[date] = Query(None, description="Date of birth strictly after YYYY-MM-DD"),
    born_before: Optional[date] = Query(None, description="Date of birth strictly before YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return crud.list_students(conn, name, course, email, born_after, born_before, limit, offset)


@app.get("/students/{student_id}", response_model=StudentOut, tags=["students"])
def get_student(student_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    student = crud.get_student(conn, student_id)
    if student is None:
        raise _not_found(student_id)
    return student


# ---------- Update ----------
@app.put("/students/{student_id}", response_model=StudentOut, tags=["students"])
@app.patch("/students/{student_id}", response_model=StudentOut, tags=["students"])
def update_student(student_id: int, payload: StudentUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    """Partial update: send only the fields you want to change (PUT and PATCH behave the same)."""
    existing = crud.get_student(conn, student_id)
    if existing is None:
        raise _not_found(student_id)
    changes = payload.model_dump(exclude_unset=True)
    merged = {**existing, **changes}
    if not merged.get("email") and not merged.get("phone"):
        raise HTTPException(status_code=422, detail="A student must keep at least one contact (email or phone)")
    try:
        return crud.update_student(conn, student_id, changes)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A student with this email already exists")


# ---------- Delete ----------
@app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["students"])
def delete_student(student_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    if not crud.delete_student(conn, student_id):
        raise _not_found(student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Optional: local AI ----------
@app.post("/ask", response_model=AskResponse, tags=["ai (optional)"])
def ask(payload: AskRequest, conn: sqlite3.Connection = Depends(get_conn)):
    """Ask a natural-language question; the answer is grounded in records fetched by backend code."""
    try:
        return ai.answer_question(conn, payload.question)
    except ai.OllamaUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

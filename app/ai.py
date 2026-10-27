"""Optional Ollama extension: natural-language questions grounded in stored records.

Safety design (per the assignment):
  * The model NEVER writes or runs SQL. Backend code maps the question to one of a
    small set of fixed, parameterised queries ("intents").
  * The retrieved rows (plus pre-computed facts such as the count) are given to the
    model as context, and the prompt tells it to answer only from that context.
"""
import os
import re
from datetime import date
from typing import Optional

import httpx

from . import crud

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
MAX_CONTEXT_ROWS = 50

YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


class OllamaUnavailable(Exception):
    pass


def classify(question: str, conn) -> tuple[str, list[dict], dict]:
    """Map a question to a fixed query. Returns (intent, rows, facts)."""
    q = question.lower()
    year_match = YEAR_RE.search(q)
    year = int(year_match.group(1)) if year_match else None
    total = crud.count_students(conn)

    if year and re.search(r"\b(after|since|later than)\b", q):
        rows = crud.list_students(conn, born_after=date(year, 12, 31), limit=MAX_CONTEXT_ROWS)
        return "born_after", rows, {"total_students": total, "born_after_year": year, "matches": len(rows)}

    if year and re.search(r"\b(before|earlier than|until)\b", q):
        rows = crud.list_students(conn, born_before=date(year, 1, 1), limit=MAX_CONTEXT_ROWS)
        return "born_before", rows, {"total_students": total, "born_before_year": year, "matches": len(rows)}

    # course filter: match any known course name mentioned in the question
    for course in _distinct_courses(conn):
        if course.lower() in q:
            rows = crud.list_students(conn, course=course, limit=MAX_CONTEXT_ROWS)
            return "by_course", rows, {"total_students": total, "course": course, "matches": len(rows)}

    if re.search(r"\b(how many|count|number of|total)\b", q):
        return "count", [], {"total_students": total}

    rows = crud.list_students(conn, limit=MAX_CONTEXT_ROWS)
    return "list_all", rows, {"total_students": total, "rows_shown": len(rows)}


def _distinct_courses(conn) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT course FROM students WHERE course IS NOT NULL ORDER BY LENGTH(course) DESC"
    ).fetchall()
    return [r[0] for r in rows]


def build_prompt(question: str, rows: list[dict], facts: dict) -> str:
    lines = [f"- id={r['id']}, name={r['name']}, dob={r['date_of_birth']}, course={r['course']}" for r in rows]
    records = "\n".join(lines) if lines else "(no individual records needed for this question)"
    facts_text = "\n".join(f"- {k}: {v}" for k, v in facts.items())
    return (
        "You are an assistant for a student database. Answer the question using ONLY the "
        "facts and records below. If the answer is not in them, say you don't know. "
        "Do not invent students or numbers. Be brief.\n\n"
        f"FACTS:\n{facts_text}\n\nRECORDS:\n{records}\n\nQUESTION: {question}\nANSWER:"
    )


def ask_ollama(prompt: str, timeout: float = 120.0) -> str:
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0}},
            timeout=timeout,
        )
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise OllamaUnavailable(
            f"Could not reach Ollama at {OLLAMA_URL}. Start it with 'ollama serve' "
            f"and pull the model with 'ollama pull {OLLAMA_MODEL}'."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaUnavailable(f"Ollama returned an error ({exc.response.status_code}): {exc.response.text[:200]}") from exc
    return resp.json().get("response", "").strip()


def answer_question(conn, question: str) -> dict:
    intent, rows, facts = classify(question, conn)
    answer = ask_ollama(build_prompt(question, rows, facts))
    return {
        "question": question,
        "answer": answer,
        "intent": intent,
        "records_used": len(rows),
        "model": OLLAMA_MODEL,
    }


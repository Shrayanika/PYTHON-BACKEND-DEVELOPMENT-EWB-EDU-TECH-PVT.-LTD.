# Students Database CRUD API

A Python backend for managing student records (Create, Read, Update, Delete) built with **FastAPI** and **SQLite**, plus an **optional** local-AI endpoint powered by **Ollama**.

> All sample data is fictional. Do not commit real student information, passwords or secrets (`*.db` and `.env` are git-ignored).

## Features

- Full CRUD on `/students` with persistent SQLite storage (`students.db`, created automatically)
- Input validation (Pydantic): required name and date of birth (must be in the past), valid email, phone format, at least one contact (email or phone)
- Clear errors: `404` missing record, `409` duplicate email, `422` invalid input
- Filtering and paging on the list endpoint
- Parameterised SQL only (no string-built queries from user input)
- Optional `/ask` endpoint: natural-language questions answered by a local Ollama model, grounded in records fetched by backend code

## Project structure

```
app/
  main.py       FastAPI routes
  schemas.py    Pydantic validation models
  crud.py       SQL access functions
  database.py   SQLite connection + schema
  ai.py         Optional Ollama extension
tests/test_api.py   pytest suite
seed.py             Loads dummy sample data
requirements.txt
```

## Prerequisites

- Python 3.10+
- (Optional, AI bonus only) [Ollama](https://ollama.com) installed

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                   # optional: loads 6 dummy students
```

## Run

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs (Swagger UI, easiest way to test): http://127.0.0.1:8000/docs

## Student fields

| Field | Required | Notes |
|---|---|---|
| `id` | auto | Unique, assigned by the database |
| `name` | yes | 1-100 chars |
| `date_of_birth` | yes | `YYYY-MM-DD`, must be in the past |
| `email` | one of email/phone | Unique |
| `phone` | one of email/phone | e.g. `+91 98000 11111` |
| `course`, `address`, `enrollment_date` | no | |

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/students` | Create a student (201) |
| GET | `/students` | List / filter students |
| GET | `/students/{student_id}` | View a student |
| PUT / PATCH | `/students/{student_id}` | Update details (send only fields to change) |
| DELETE | `/students/{student_id}` | Delete a student (204) |
| POST | `/ask` | Optional: ask a question using Ollama |

List filters (query params): `name`, `course` (partial, case-insensitive), `email` (exact), `born_after`, `born_before` (`YYYY-MM-DD`), `limit` (default 100), `offset`.

## Testing the API with curl

```bash
# Create
curl -X POST http://127.0.0.1:8000/students -H "Content-Type: application/json" \
  -d '{"name":"Asha Verma","date_of_birth":"2005-08-19","email":"asha@example.com","course":"Python Backend"}'

# List and filter
curl http://127.0.0.1:8000/students
curl "http://127.0.0.1:8000/students?course=python&born_after=2004-12-31"

# View one
curl http://127.0.0.1:8000/students/1

# Update (only the changed field)
curl -X PATCH http://127.0.0.1:8000/students/1 -H "Content-Type: application/json" \
  -d '{"course":"Data Analytics"}'

# Delete
curl -X DELETE http://127.0.0.1:8000/students/1

# Missing record -> 404
curl -i http://127.0.0.1:8000/students/9999
```

## Automated tests

```bash
pytest -q
```

The tests use a temporary database, so your `students.db` is never touched. Ollama is mocked in the tests.

## Optional bonus: local AI with Ollama

```bash
ollama pull llama3.2:1b
ollama serve                      # skip if it is already running
```

```bash
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"question":"List students born after 2005"}'
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"question":"How many students are there?"}'
```

Response example: `{"question": "...", "answer": "...", "intent": "born_after", "records_used": 2, "model": "llama3.2:1b"}`

Settings (environment variables): `OLLAMA_URL` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `llama3.2:1b`).

### How it stays safe and accurate

1. **The model never writes SQL.** Backend code maps the question to one of a few fixed, parameterised queries (`count`, `born_after`, `born_before`, `by_course`, `list_all`).
2. The matching rows, plus pre-computed facts such as the total count, are passed to the model as context. Small models are unreliable at counting, so the count comes from the database, not the model.
3. The prompt instructs the model to answer only from that context and to say so when the answer is not there.
4. If Ollama is not running, `/ask` returns a clear `503` message; the CRUD API is unaffected.

Supported question styles: counts ("how many students"), birth year ("born after 2005", "born before 2004"), course ("who is in Data Analytics"), and general listing.

## Architecture notes (for the demo)

- **Create:** `POST /students` -> Pydantic validates -> `crud.create_student` runs a parameterised `INSERT` -> returns the stored row with its new `id`.
- **Update:** the existing row is loaded, changes are merged to check the "at least one contact" rule, then a whitelisted-column `UPDATE` runs.
- **Delete:** `DELETE ... WHERE id = ?`; a `404` is returned if nothing was removed.
- **Persistence:** every change is committed to `students.db`, so data survives restarts.

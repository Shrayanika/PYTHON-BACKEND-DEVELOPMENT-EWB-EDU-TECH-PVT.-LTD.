import pytest
from fastapi.testclient import TestClient

from app import ai
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:  # triggers lifespan -> creates tables in the temp DB
        yield c


def make(client, **overrides):
    payload = {
        "name": "Test Student",
        "date_of_birth": "2004-05-20",
        "email": "test@example.com",
        "course": "Python Backend",
    }
    payload.update(overrides)
    return client.post("/students", json=payload)


# ---------- Create ----------
def test_create_student(client):
    r = make(client)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1 and body["name"] == "Test Student"


def test_create_requires_contact(client):
    r = make(client, email=None)
    assert r.status_code == 422


def test_create_with_phone_only(client):
    r = make(client, email=None, phone="+91 98000 12345")
    assert r.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"email": "not-an-email"},
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": "not-a-date"},
        {"phone": "abc"},
    ],
)
def test_create_validation_errors(client, overrides):
    assert make(client, **overrides).status_code == 422


def test_duplicate_email_conflict(client):
    assert make(client).status_code == 201
    assert make(client, name="Other").status_code == 409


# ---------- Read ----------
def test_list_and_get(client):
    make(client)
    make(client, name="Second", email="second@example.com", course="Data Analytics")
    assert len(client.get("/students").json()) == 2
    r = client.get("/students/2")
    assert r.status_code == 200 and r.json()["name"] == "Second"


def test_get_missing_is_404(client):
    assert client.get("/students/999").status_code == 404


def test_filters(client):
    make(client, name="Alice Brown", email="a@example.com", course="Data Analytics", date_of_birth="2006-01-01")
    make(client, name="Bob Green", email="b@example.com", course="Python Backend", date_of_birth="2003-01-01")
    assert [s["name"] for s in client.get("/students", params={"name": "alice"}).json()] == ["Alice Brown"]
    assert [s["name"] for s in client.get("/students", params={"course": "python"}).json()] == ["Bob Green"]
    assert [s["name"] for s in client.get("/students", params={"born_after": "2005-01-01"}).json()] == ["Alice Brown"]
    assert [s["name"] for s in client.get("/students", params={"born_before": "2005-01-01"}).json()] == ["Bob Green"]
    assert client.get("/students", params={"email": "B@EXAMPLE.COM"}).json()[0]["name"] == "Bob Green"


def test_sql_injection_in_filter_is_harmless(client):
    make(client)
    r = client.get("/students", params={"name": "'; DROP TABLE students; --"})
    assert r.status_code == 200 and r.json() == []
    assert len(client.get("/students").json()) == 1


# ---------- Update ----------
def test_patch_and_put(client):
    make(client)
    r = client.patch("/students/1", json={"course": "Web Development"})
    assert r.status_code == 200
    assert r.json()["course"] == "Web Development" and r.json()["name"] == "Test Student"
    r = client.put("/students/1", json={"name": "Renamed"})
    assert r.json()["name"] == "Renamed"
    assert client.get("/students/1").json()["name"] == "Renamed"  # persisted


def test_update_missing_is_404(client):
    assert client.patch("/students/42", json={"name": "X"}).status_code == 404


def test_update_validation(client):
    make(client)
    assert client.patch("/students/1", json={"email": "bad"}).status_code == 422
    assert client.patch("/students/1", json={"name": None}).status_code == 422


def test_update_cannot_remove_last_contact(client):
    make(client)
    assert client.patch("/students/1", json={"email": None}).status_code == 422


def test_update_to_duplicate_email_conflict(client):
    make(client)
    make(client, name="Two", email="two@example.com")
    assert client.patch("/students/2", json={"email": "test@example.com"}).status_code == 409


# ---------- Delete ----------
def test_delete(client):
    make(client)
    assert client.delete("/students/1").status_code == 204
    assert client.get("/students/1").status_code == 404
    assert client.delete("/students/1").status_code == 404


# ---------- Persistence ----------
def test_data_persists_across_app_restarts(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "persist.db"))
    with TestClient(app) as c:
        make(c)
    with TestClient(app) as c2:  # fresh startup, same file
        assert c2.get("/students/1").json()["name"] == "Test Student"


# ---------- Optional AI (Ollama is mocked) ----------
def test_ask_grounds_prompt_in_db_records(client, monkeypatch):
    make(client, name="Old One", email="o@example.com", date_of_birth="2003-02-02")
    make(client, name="Young One", email="y@example.com", date_of_birth="2006-02-02")
    seen = {}

    def fake(prompt, timeout=120.0):
        seen["prompt"] = prompt
        return "Young One"

    monkeypatch.setattr(ai, "ask_ollama", fake)
    r = client.post("/ask", json={"question": "List students born after 2005"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "born_after" and body["records_used"] == 1
    assert "Young One" in seen["prompt"] and "Old One" not in seen["prompt"]


def test_ask_count_uses_precomputed_total(client, monkeypatch):
    make(client)
    make(client, name="B", email="b@example.com")
    monkeypatch.setattr(ai, "ask_ollama", lambda p, timeout=120.0: p)
    r = client.post("/ask", json={"question": "How many students are there?"})
    assert r.json()["intent"] == "count"
    assert "total_students: 2" in r.json()["answer"]


def test_ask_returns_503_when_ollama_down(client, monkeypatch):
    monkeypatch.setattr(ai, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here
    r = client.post("/ask", json={"question": "How many students are there?"})
    assert r.status_code == 503
    assert "ollama" in r.json()["detail"].lower()


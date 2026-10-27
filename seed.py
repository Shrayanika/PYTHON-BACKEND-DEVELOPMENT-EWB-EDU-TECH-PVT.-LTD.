"""Load DUMMY sample data (all names/contacts are fictional). Run: python seed.py"""
from app.database import connect, init_db
from app import crud

SAMPLE = [
    {"name": "Aarav Sharma", "date_of_birth": "2004-03-14", "email": "aarav.sharma@example.com", "phone": "+91 98000 11111", "course": "Python Backend", "address": "12 Lake Road, Kolkata", "enrollment_date": "2024-07-01"},
    {"name": "Diya Patel", "date_of_birth": "2005-11-02", "email": "diya.patel@example.com", "phone": None, "course": "Data Analytics", "address": None, "enrollment_date": "2024-07-01"},
    {"name": "Rohan Das", "date_of_birth": "2006-06-21", "email": "rohan.das@example.com", "phone": "+91 98000 22222", "course": "Python Backend", "address": "5 Park Street, Kolkata", "enrollment_date": "2025-01-10"},
    {"name": "Meera Iyer", "date_of_birth": "2003-01-30", "email": None, "phone": "+91 98000 33333", "course": "Web Development", "address": None, "enrollment_date": "2023-07-15"},
    {"name": "Kabir Singh", "date_of_birth": "2007-09-09", "email": "kabir.singh@example.com", "phone": None, "course": "Data Analytics", "address": "88 Hill View, Siliguri", "enrollment_date": "2025-07-01"},
    {"name": "Ananya Roy", "date_of_birth": "2005-04-17", "email": "ananya.roy@example.com", "phone": "+91 98000 44444", "course": "Web Development", "address": None, "enrollment_date": "2024-01-08"},
]


def main() -> None:
    init_db()
    conn = connect()
    if crud.count_students(conn) > 0:
        print("Database already has data; skipping seed.")
        return
    for row in SAMPLE:
        crud.create_student(conn, row)
    print(f"Inserted {len(SAMPLE)} dummy students.")


if __name__ == "__main__":
    main()

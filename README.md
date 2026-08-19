# gps-attendance

A GPS self-attendance system for classrooms. Students mark their own
attendance from their phone, and the server verifies they are actually in
the room.

Attendance is only possible while the teacher has the window open, and a
record requires several independent proofs of presence rather than
location alone:

| Layer | What it checks |
| --- | --- |
| Teacher window | Nothing is possible until the teacher opens it, ~120s |
| Rotating token | A QR code on the classroom screen, valid ~30s |
| Classroom network | The request must come from the classroom Wi-Fi |
| Device binding | One account, one registered phone |
| Geofence | 10 m, centred on the teacher, accuracy aware |
| Attempt log | Every attempt recorded, successful or not |

## Documentation

- [GPS_Self_Attendance_System_README.md](GPS_Self_Attendance_System_README.md)
  is the full design document: architecture, database schema, API,
  validation rules, and the reasoning behind the anti-proxy design.
- [DEPLOY.md](DEPLOY.md) covers deploying to Railway with Postgres.

## Running locally

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
python seed.py
python app.py
```

Then open http://127.0.0.1:5000

The seeded accounts and their passwords are printed by `seed.py`. They are
demo credentials and must be replaced before any real use.

## Tests

```bash
pytest -q
```

125 tests covering the geofence maths, the teacher gate, the anti-proxy
layers, and client IP resolution behind a proxy.

## Stack

Python 3.10+, Flask, SQLAlchemy, SQLite locally and Postgres in
production. No frontend build step.

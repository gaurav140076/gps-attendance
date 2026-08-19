"""Shared test fixtures."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from extensions import db  # noqa: E402
from models.academic import ClassGroup, Department, Subject  # noqa: E402
from models.location import Location  # noqa: E402
from models.people import Student, Teacher  # noqa: E402
from models.session import AttendanceSession  # noqa: E402

PASSWORD = "password123"

# The Flask test client presents 127.0.0.1, so the seeded classroom
# accepts loopback. The network layer stays enforced -- switching it off
# for tests would stop the tests testing it.
TEST_NETWORKS = "127.0.0.1/32"


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def data(app):
    """A department, class, subject, classroom, teacher and two students."""
    dept = Department(name="Computer Science")
    db.session.add(dept)
    db.session.flush()

    klass = ClassGroup(name="CSE 3A", department_id=dept.id, year=3, section="A")
    other = ClassGroup(name="CSE 3B", department_id=dept.id, year=3, section="B")
    subject = Subject(name="Data Structures", code="CS301", department_id=dept.id)
    db.session.add_all([klass, other, subject])
    db.session.flush()

    room = Location(
        name="CS Block - Room 204",
        latitude=28.613900,
        longitude=77.209000,
        radius_meters=10,
        allowed_networks=TEST_NETWORKS,
    )
    db.session.add(room)

    teacher = Teacher(name="Mr. Sharma", email="sharma@college.edu")
    teacher.set_password(PASSWORD)
    db.session.add(teacher)
    db.session.flush()

    gaurav = Student(
        name="Gaurav Roy", roll_no="101", email="101@college.edu",
        department_id=dept.id, class_id=klass.id,
    )
    gaurav.set_password(PASSWORD)

    priya = Student(
        name="Priya Nair", roll_no="102", email="102@college.edu",
        department_id=dept.id, class_id=klass.id,
    )
    priya.set_password(PASSWORD)

    outsider = Student(
        name="Vikram Rao", roll_no="201", email="201@college.edu",
        department_id=dept.id, class_id=other.id,
    )
    outsider.set_password(PASSWORD)

    db.session.add_all([gaurav, priya, outsider])
    db.session.commit()

    session = AttendanceSession(
        teacher_id=teacher.id,
        class_id=klass.id,
        subject_id=subject.id,
        location_id=room.id,
    )
    db.session.add(session)
    db.session.commit()

    return {
        "dept": dept,
        "class": klass,
        "other_class": other,
        "subject": subject,
        "room": room,
        "teacher": teacher,
        "student": gaurav,
        "student2": priya,
        "outsider": outsider,
        "session": session,
    }


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email, role="STUDENT"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD, "role": role},
    )


def register_device(client):
    return client.post("/api/student/device/register", json={"fingerprint": "pytest"})


def student_client(app, email):
    """A logged-in student whose device is registered."""
    c = app.test_client()
    login(c, email)
    register_device(c)
    return c


def teacher_client(app, email):
    c = app.test_client()
    login(c, email, role="TEACHER")
    return c


def mark(client, session_id, token, lat=28.613935, lon=77.209021, accuracy=8.4, **extra):
    body = {
        "session_id": session_id,
        "token": token,
        "latitude": lat,
        "longitude": lon,
        "accuracy": accuracy,
    }
    body.update(extra)
    return client.post("/api/attendance/mark", json=body)

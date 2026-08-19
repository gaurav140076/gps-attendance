"""The teacher gate: TG01-TG09 from the README.

A student can mark attendance only once the teacher turns it on.
"""

from datetime import timedelta

import pytest

from conftest import mark, student_client, teacher_client
from extensions import db
from models.session import ACTIVE, CLOSED, SCHEDULED
from services import token_service, window_service
from util import utcnow


def open_and_token(app, data, window_seconds=120):
    """Open the window and return the live token."""
    session = data["session"]
    window_service.open_window(session, window_seconds, 300)
    return token_service.current_token(session).token


# --- TG01/TG02: nothing is possible before the teacher opens ------------

def test_tg01_scheduled_session_refuses_everyone(app, data):
    assert data["session"].status == SCHEDULED

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, "anything")

    assert response.status_code == 403
    assert response.get_json()["error"] == "WINDOW_NOT_OPEN"


def test_tg02_crafted_request_for_unknown_session_is_refused(app, data):
    client = student_client(app, "101@college.edu")
    response = mark(client, 99999, "anything")

    assert response.status_code == 404
    assert response.get_json()["error"] == "SESSION_NOT_FOUND"


def test_student_sees_no_open_sessions_before_the_teacher_opens(app, data):
    client = student_client(app, "101@college.edu")
    body = client.get("/api/student/sessions").get_json()
    assert body["sessions"] == []


# --- TG03: opening the window lets attendance through -------------------

def test_tg03_open_window_allows_marking(app, data):
    token = open_and_token(app, data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, token)

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["status"] == "PRESENT"
    assert body["allowed_radius"] == 10


def test_student_sees_the_session_once_open(app, data):
    open_and_token(app, data)
    client = student_client(app, "101@college.edu")

    sessions = client.get("/api/student/sessions").get_json()["sessions"]

    assert len(sessions) == 1
    assert sessions[0]["subject"] == "Data Structures"
    assert sessions[0]["seconds_remaining"] > 0


# --- TG04/TG05: closing and expiry both stop attendance -----------------

def test_tg04_closing_the_window_stops_marking(app, data):
    token = open_and_token(app, data)
    window_service.close_window(data["session"])

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, token)

    assert response.status_code == 403
    assert response.get_json()["error"] in ("WINDOW_NOT_OPEN", "WINDOW_EXPIRED")


def test_tg05_expired_window_refuses_marking(app, data):
    session = data["session"]
    token = open_and_token(app, data)

    # Wind the clock past the deadline.
    session.closes_at = utcnow() - timedelta(seconds=1)
    db.session.commit()

    client = student_client(app, "101@college.edu")
    response = mark(client, session.id, token)

    assert response.status_code == 403
    assert response.get_json()["error"] in ("WINDOW_NOT_OPEN", "WINDOW_EXPIRED")


def test_tg06_stale_active_session_auto_closes(app, data):
    """A session left ACTIVE by a crashed process must not stay open."""
    session = data["session"]
    open_and_token(app, data)

    session.closes_at = utcnow() - timedelta(seconds=5)
    db.session.commit()

    window_service.expire_if_due(session)

    assert session.status == CLOSED
    assert session.closed_at is not None


def test_status_alone_is_not_enough(app, data):
    """The timestamp check is load-bearing, not decorative."""
    session = data["session"]
    open_and_token(app, data)

    session.closes_at = utcnow() - timedelta(seconds=1)
    db.session.commit()

    assert session.status == ACTIVE  # still says ACTIVE...
    assert session.is_window_open() is False  # ...but the window is shut


# --- TG07: no tokens while shut -----------------------------------------

def test_tg07_token_endpoint_refuses_when_window_shut(app, data):
    client = teacher_client(app, "sharma@college.edu")
    response = client.get(f"/api/teacher/sessions/{data['session'].id}/token")

    assert response.status_code == 403
    assert response.get_json()["error"] == "WINDOW_NOT_OPEN"


def test_no_token_is_minted_for_a_closed_session(app, data):
    assert token_service.current_token(data["session"]) is None


# --- TG08: only the owning teacher may open -----------------------------

def test_tg08_other_teacher_cannot_open_the_window(app, data):
    from models.people import Teacher

    intruder = Teacher(name="Ms. Das", email="das@college.edu")
    intruder.set_password("password123")
    db.session.add(intruder)
    db.session.commit()

    client = teacher_client(app, "das@college.edu")
    response = client.post(f"/api/teacher/sessions/{data['session'].id}/open", json={})

    assert response.status_code == 403


def test_student_cannot_open_the_window(app, data):
    client = student_client(app, "101@college.edu")
    response = client.post(f"/api/teacher/sessions/{data['session'].id}/open", json={})

    assert response.status_code == 403


# --- TG09: CLOSED is terminal -------------------------------------------

def test_tg09_closed_session_cannot_be_reopened(app, data):
    session = data["session"]
    open_and_token(app, data)
    window_service.close_window(session)

    with pytest.raises(window_service.WindowError) as exc:
        window_service.open_window(session, 120, 300)

    assert exc.value.code == "SESSION_CLOSED"


def test_closing_invalidates_outstanding_tokens(app, data):
    """A code photographed just before Close must not still work."""
    session = data["session"]
    token = open_and_token(app, data)

    window_service.close_window(session)

    row, error = token_service.validate(session, token)
    assert row is None
    assert error == "TOKEN_EXPIRED"


# --- Window length ------------------------------------------------------

def test_window_length_is_clamped_to_the_maximum(app, data):
    """The ceiling exists because a long window hands back the time
    budget that makes proxy impractical."""
    session = data["session"]
    window_service.open_window(session, 9999, 300)

    assert session.window_seconds == 300
    assert (session.closes_at - session.opened_at).total_seconds() == 300


def test_absurdly_short_window_is_rejected(app, data):
    with pytest.raises(window_service.WindowError):
        window_service.open_window(data["session"], 2, 300)


def test_reopening_an_active_window_is_refused(app, data):
    window_service.open_window(data["session"], 120, 300)
    with pytest.raises(window_service.WindowError) as exc:
        window_service.open_window(data["session"], 120, 300)
    assert exc.value.code == "ALREADY_OPEN"

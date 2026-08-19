"""The anti-proxy layers: AP01-AP16 from the README.

Each test defeats exactly one layer and confirms the chain still refuses.
That is the whole claim of the design -- every layer must be defeated at
once, not one at a time.
"""

from datetime import timedelta

from conftest import login, mark, register_device, student_client, teacher_client
from extensions import db
from models.attendance import Attendance, AttendanceAttempt
from models.location import Location
from models.session import AttendanceSession
from services import token_service, window_service
from util import utcnow


def open_and_token(data, window_seconds=120):
    window_service.open_window(data["session"], window_seconds, 300)
    return token_service.current_token(data["session"]).token


# --- Layer 2: the rotating token ----------------------------------------

def test_ap01_expired_token_is_refused(app, data):
    """The screenshot-to-an-absent-friend attack."""
    token = open_and_token(data)

    row = token_service.validate(data["session"], token)[0]
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.session.commit()

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, token)

    assert response.status_code == 403
    assert response.get_json()["error"] == "TOKEN_EXPIRED"


def test_expired_token_failure_is_marked_retryable(app, data):
    """An honest student whose camera was slow must not lose the class."""
    token = open_and_token(data)
    row = token_service.validate(data["session"], token)[0]
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.session.commit()

    client = student_client(app, "101@college.edu")
    body = mark(client, data["session"].id, token).get_json()

    assert body["retryable"] is True


def test_ap02_token_from_another_session_is_refused(app, data):
    open_and_token(data)

    other = AttendanceSession(
        teacher_id=data["teacher"].id,
        class_id=data["class"].id,
        subject_id=data["subject"].id,
        location_id=data["room"].id,
    )
    db.session.add(other)
    db.session.commit()
    window_service.open_window(other, 120, 300)
    foreign = token_service.current_token(other).token

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, foreign)

    assert response.get_json()["error"] == "TOKEN_INVALID"


def test_ap03_missing_token_is_refused(app, data):
    open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, "")

    assert response.get_json()["error"] == "TOKEN_MISSING"


def test_ap04_guessed_token_is_refused(app, data):
    open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, "ZZZZZZ")

    assert response.get_json()["error"] == "TOKEN_INVALID"


def test_tokens_are_unpredictable(app, data):
    """A token derived from the clock could be computed from home."""
    session = data["session"]
    window_service.open_window(session, 120, 300)

    tokens = {token_service.issue_token(session).token for _ in range(20)}

    assert len(tokens) == 20
    assert all(len(t) > 20 for t in tokens)


def test_short_code_also_works(app, data):
    """The typed fallback, for a camera that will not focus."""
    open_and_token(data)
    code = token_service.current_token(data["session"]).display_code

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, code)

    assert response.get_json()["success"] is True


# --- Layer 3: the classroom network --------------------------------------

def test_ap05_request_from_off_campus_is_refused(app, data):
    """Perfect GPS, wrong network. The coordinates never get evaluated."""
    token = open_and_token(data)
    data["room"].allowed_networks = "203.0.113.0/24"
    db.session.commit()

    client = student_client(app, "101@college.edu")
    response = mark(
        client, data["session"].id, token,
        lat=28.613900, lon=77.209000, accuracy=4.0,  # dead on the classroom
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "WRONG_NETWORK"


def test_ap06_forwarded_header_is_not_trusted(app, data):
    """Spoofing X-Forwarded-For must not grant classroom access."""
    token = open_and_token(data)
    data["room"].allowed_networks = "203.0.113.44/32"
    db.session.commit()

    client = student_client(app, "101@college.edu")
    response = client.post(
        "/api/attendance/mark",
        json={
            "session_id": data["session"].id,
            "token": token,
            "latitude": 28.613935,
            "longitude": 77.209021,
            "accuracy": 8.4,
        },
        headers={"X-Forwarded-For": "203.0.113.44"},
    )

    assert response.get_json()["error"] == "WRONG_NETWORK"


def test_location_with_no_networks_fails_closed(app, data):
    """"Not configured" must never mean "allow"."""
    token = open_and_token(data)
    data["room"].allowed_networks = ""
    db.session.commit()

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, token)

    assert response.get_json()["error"] == "NETWORK_NOT_CONFIGURED"


# --- Layers 4 and 5: device binding ---------------------------------------

def test_ap08_unregistered_device_is_refused(app, data):
    """The friend logging in on their own phone."""
    token = open_and_token(data)

    client = app.test_client()
    login(client, "101@college.edu")  # logged in, but never registered

    response = mark(client, data["session"].id, token)

    assert response.get_json()["error"] == "DEVICE_NOT_REGISTERED"


def test_ap09_one_device_cannot_mark_two_students(app, data):
    """Passing one unlocked phone around the room."""
    token = open_and_token(data)

    client = student_client(app, "101@college.edu")
    assert mark(client, data["session"].id, token).get_json()["success"] is True

    # Same browser (same device cookie), different account.
    client.get("/api/auth/logout")
    login(client, "102@college.edu")

    response = mark(client, data["session"].id, token)
    body = response.get_json()

    assert body["success"] is False
    assert body["error"] in ("DEVICE_NOT_REGISTERED", "DEVICE_ALREADY_USED")


def test_device_cannot_be_registered_to_two_students(app, data):
    client = student_client(app, "101@college.edu")

    client.get("/api/auth/logout")
    login(client, "102@college.edu")
    response = register_device(client)

    assert response.status_code == 409
    assert response.get_json()["error"] == "DEVICE_OWNED_BY_ANOTHER_STUDENT"


def test_device_identity_cannot_be_supplied_in_the_body(app, data):
    """The client may present a device, never choose one."""
    token = open_and_token(data)

    victim = student_client(app, "101@college.edu")
    victim_hash = data["student"].active_device().device_hash

    attacker = app.test_client()
    login(attacker, "102@college.edu")

    response = mark(
        attacker, data["session"].id, token, device_hash=victim_hash
    )

    assert response.get_json()["error"] == "DEVICE_NOT_REGISTERED"


# --- Layer 6: enrolment ---------------------------------------------------

def test_ap_student_from_another_class_is_refused(app, data):
    token = open_and_token(data)
    client = student_client(app, "201@college.edu")

    response = mark(client, data["session"].id, token)

    assert response.get_json()["error"] == "NOT_ENROLLED"


# --- Layer 7: location sanity ---------------------------------------------

def test_ap10_mock_location_flag_is_refused(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, token, is_mock=True)

    assert response.get_json()["error"] == "INVALID_LOCATION"


def test_invalid_coordinates_are_refused(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, token, lat=999, lon=999)

    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_LOCATION"


def test_ap11_exact_coordinates_are_recorded_present_with_the_signal_kept(app, data):
    """Suspicious, but attendance still counts.

    The heuristic fires on honest cases too -- two browser windows on one
    laptop report byte-identical coordinates -- so it records the signal
    rather than withholding the record.
    """
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(
        client, data["session"].id, token,
        lat=data["room"].latitude, lon=data["room"].longitude, accuracy=4.0,
    )
    body = response.get_json()

    assert body["success"] is True
    assert body["status"] == "PRESENT"
    assert "EXACT_CLASSROOM_MATCH" in body["flags"]

    # The signal must survive on the row, or the teacher loses the ability
    # to review it later.
    record = Attendance.query.filter_by(student_id=data["student"].id).first()
    assert "EXACT_CLASSROOM_MATCH" in record.verification_flags


def test_flagging_can_be_switched_back_on(app, data):
    """FLAG_SUSPICIOUS_RECORDS holds suspicious records for review."""
    app.config["FLAG_SUSPICIOUS_RECORDS"] = True

    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    body = mark(
        client, data["session"].id, token,
        lat=data["room"].latitude, lon=data["room"].longitude, accuracy=4.0,
    ).get_json()

    assert body["success"] is True
    assert body["status"] == "FLAGGED"


# --- Geofence in the chain -------------------------------------------------

def test_outside_the_radius_is_refused_with_distance(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    # ~180 m north of the classroom.
    response = mark(
        client, data["session"].id, token,
        lat=28.615520, lon=77.209000, accuracy=10.0,
    )
    body = response.get_json()

    assert body["error"] == "OUTSIDE_RADIUS"
    assert body["allowed_radius"] == 10
    assert body["distance_meters"] > 100


def test_poor_accuracy_asks_for_a_retry(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    response = mark(client, data["session"].id, token, accuracy=90.0)
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "POOR_ACCURACY"
    assert body["retryable"] is True


# --- Duplicates and races ---------------------------------------------------

def test_duplicate_attendance_is_refused(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")

    assert mark(client, data["session"].id, token).get_json()["success"] is True
    response = mark(client, data["session"].id, token)

    assert response.status_code == 409
    assert response.get_json()["error"] == "ALREADY_MARKED"


def test_ap14_unique_constraint_prevents_double_records(app, data):
    """The database is the real guarantee, not the application check."""
    import sqlalchemy

    token = open_and_token(data)
    client = student_client(app, "101@college.edu")
    mark(client, data["session"].id, token)

    duplicate = Attendance(
        student_id=data["student"].id,
        session_id=data["session"].id,
        date=utcnow().date(),
        time=utcnow().time(),
    )
    db.session.add(duplicate)

    try:
        raised = False
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        raised = True
        db.session.rollback()

    assert raised, "the (student_id, session_id) unique constraint did not fire"


def test_ap15_device_session_uniqueness_is_enforced_in_the_database(app, data):
    import sqlalchemy

    token = open_and_token(data)
    client = student_client(app, "101@college.edu")
    mark(client, data["session"].id, token)

    device_id = data["student"].active_device().id

    clash = Attendance(
        student_id=data["student2"].id,
        session_id=data["session"].id,
        device_id=device_id,
        date=utcnow().date(),
        time=utcnow().time(),
    )
    db.session.add(clash)

    try:
        raised = False
        db.session.commit()
    except sqlalchemy.exc.IntegrityError:
        raised = True
        db.session.rollback()

    assert raised, "the (device_id, session_id) unique constraint did not fire"


# --- Rate limiting -----------------------------------------------------------

def test_ap13_repeated_attempts_are_rate_limited(app, data):
    open_and_token(data)
    client = student_client(app, "101@college.edu")

    codes = []
    for _ in range(12):
        codes.append(mark(client, data["session"].id, "WRONGCODE").get_json()["error"])

    assert "RATE_LIMITED" in codes


# --- Layer 8: everything is logged ------------------------------------------

def test_ap16_every_rejection_is_logged(app, data):
    token = open_and_token(data)
    data["room"].allowed_networks = "203.0.113.0/24"
    db.session.commit()

    client = student_client(app, "101@college.edu")
    mark(client, data["session"].id, token)

    attempt = AttendanceAttempt.query.filter_by(
        session_id=data["session"].id
    ).order_by(AttendanceAttempt.id.desc()).first()

    assert attempt is not None
    assert attempt.result == "REJECTED"
    assert attempt.failure_reason == "WRONG_NETWORK"
    assert attempt.source_ip == "127.0.0.1"


def test_successful_attendance_is_logged_too(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")
    mark(client, data["session"].id, token)

    accepted = AttendanceAttempt.query.filter_by(result="ACCEPTED").first()

    assert accepted is not None
    assert accepted.student_id == data["student"].id


def test_record_carries_the_full_audit_trail(app, data):
    token = open_and_token(data)
    client = student_client(app, "101@college.edu")
    mark(client, data["session"].id, token)

    record = Attendance.query.filter_by(student_id=data["student"].id).first()

    assert record.device_id is not None
    assert record.token_id is not None
    assert record.source_ip == "127.0.0.1"
    assert "WINDOW_OK" in record.verification_flags
    assert "TOKEN_OK" in record.verification_flags
    assert "NETWORK_OK" in record.verification_flags
    assert "DEVICE_OK" in record.verification_flags
    assert "GEOFENCE_OK" in record.verification_flags


# --- Authorisation -----------------------------------------------------------

def test_anonymous_request_is_refused(app, data):
    open_and_token(data)
    client = app.test_client()

    response = client.post(
        "/api/attendance/mark",
        json={"session_id": data["session"].id, "token": "x",
              "latitude": 28.6, "longitude": 77.2, "accuracy": 5},
    )

    assert response.status_code == 401


def test_student_cannot_read_the_teacher_roster(app, data):
    client = student_client(app, "101@college.edu")
    response = client.get(f"/api/teacher/sessions/{data['session'].id}/attendance")
    assert response.status_code == 403


def test_student_cannot_reach_admin_endpoints(app, data):
    client = student_client(app, "101@college.edu")
    assert client.get("/api/admin/students").status_code == 403


def test_teacher_cannot_reach_admin_endpoints(app, data):
    client = teacher_client(app, "sharma@college.edu")
    assert client.get("/api/admin/attempts").status_code == 403


# --- Teacher override ---------------------------------------------------------

def test_override_marks_a_student_and_records_who_did_it(app, data):
    open_and_token(data)
    client = teacher_client(app, "sharma@college.edu")

    response = client.post(
        f"/api/teacher/sessions/{data['session'].id}/override",
        json={"student_id": data["student"].id, "present": True,
              "note": "phone battery died"},
    )

    assert response.get_json()["success"] is True

    record = Attendance.query.filter_by(student_id=data["student"].id).first()
    assert record.status == "PRESENT"
    assert record.is_override is True
    assert record.override_by == data["teacher"].id
    assert record.override_note == "phone battery died"


def test_override_refuses_a_student_from_another_class(app, data):
    client = teacher_client(app, "sharma@college.edu")
    response = client.post(
        f"/api/teacher/sessions/{data['session'].id}/override",
        json={"student_id": data["outsider"].id},
    )
    assert response.status_code == 404

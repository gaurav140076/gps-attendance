"""The attendance verification chain.

Layers are evaluated in a deliberate order: the cheap, unspoofable checks
run before the expensive, spoofable ones. A student marking from home
fails on the network check and their perfect coordinates are never even
looked at.

Every outcome -- accepted, rejected or flagged -- is written to the
attempt log. A rejection that leaves no trace teaches nobody anything.
"""

from dataclasses import dataclass, field
from datetime import date as date_cls

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.attendance import FLAGGED, PRESENT, REJECTED, Attendance, AttendanceAttempt
from models.session import AttendanceSession
from services import anomaly_service, device_service, network_service, token_service
from services.geolocation import (
    INSIDE,
    OUTSIDE,
    RETRY_POOR_ACCURACY,
    check_geofence,
    distance_to_anchor,
    valid_coordinates,
)
from services.window_service import expire_if_due
from util import utcnow

# User-facing text for every failure the chain can produce. Saying which
# layer failed and what to do about it keeps honest Wi-Fi problems from
# becoming something the teacher has to debug mid-lecture.
MESSAGES = {
    "SESSION_NOT_FOUND": "That attendance session does not exist.",
    "WINDOW_NOT_OPEN": (
        "Your teacher has not opened attendance yet. The button will appear "
        "as soon as the attendance window starts."
    ),
    "WINDOW_EXPIRED": (
        "The attendance window has closed. Please speak to your teacher if "
        "you were present but could not mark in time."
    ),
    "RATE_LIMITED": "Too many attempts. Please wait a moment before trying again.",
    "TOKEN_MISSING": "Scan the QR code on the classroom screen first.",
    "TOKEN_EXPIRED": (
        "That code has already changed. Point your camera at the screen "
        "again -- it refreshes every few seconds."
    ),
    "TOKEN_INVALID": "That code is not valid for this session.",
    "WRONG_NETWORK": (
        "You must be connected to the classroom Wi-Fi network to mark "
        "attendance."
    ),
    "NETWORK_NOT_CONFIGURED": (
        "This classroom has no network registered yet. Ask your teacher to "
        "mark you manually and tell the administrator."
    ),
    "DEVICE_NOT_REGISTERED": (
        "This device is not registered to your account. Attendance can only "
        "be marked from your registered device."
    ),
    "DEVICE_ALREADY_USED": (
        "This device has already marked attendance for another student in "
        "this session."
    ),
    "NOT_ENROLLED": "You are not enrolled in the class for this session.",
    "INVALID_LOCATION": "Your location could not be verified.",
    "POOR_ACCURACY": (
        "Your GPS accuracy is too low. Move away from the window or wait a "
        "moment, then try again."
    ),
    "OUTSIDE_RADIUS": "You are outside the classroom attendance area.",
    "ALREADY_MARKED": "Attendance has already been marked for this session.",
}

# Failures the student should retry rather than give up on.
RETRYABLE = {"TOKEN_EXPIRED", "TOKEN_MISSING", "POOR_ACCURACY", "RATE_LIMITED"}


@dataclass
class MarkResult:
    success: bool
    error: str = None
    message: str = ""
    status_code: int = 200
    distance_meters: float = None
    effective_meters: float = None
    allowed_radius: int = None
    attendance_id: int = None
    record_status: str = None
    flags: list = field(default_factory=list)
    accuracy: float = None
    max_accuracy: int = None

    def to_dict(self):
        payload = {"success": self.success, "message": self.message}
        if self.error:
            payload["error"] = self.error
            payload["retryable"] = self.error in RETRYABLE
        if self.accuracy is not None:
            payload["accuracy"] = round(self.accuracy, 1)
        if self.max_accuracy is not None:
            payload["max_accuracy"] = self.max_accuracy
        if self.distance_meters is not None:
            payload["distance_meters"] = round(self.distance_meters, 1)
        if self.effective_meters is not None:
            payload["effective_meters"] = round(self.effective_meters, 1)
        if self.allowed_radius is not None:
            payload["allowed_radius"] = self.allowed_radius
        if self.attendance_id is not None:
            payload["attendance_id"] = self.attendance_id
        if self.record_status:
            payload["status"] = self.record_status
        if self.flags:
            payload["flags"] = self.flags
        return payload


def _log(student, session, result, reason, lat=None, lon=None, accuracy=None,
         distance=None, device_hash=None, ip=None, note=None):
    """Record an attempt. Never allowed to break the response."""
    try:
        db.session.add(
            AttendanceAttempt(
                student_id=student.id if student else None,
                session_id=session.id if session else None,
                result=result,
                failure_reason=reason,
                latitude=lat,
                longitude=lon,
                accuracy=accuracy,
                distance_meters=distance,
                device_hash=device_hash,
                source_ip=ip,
                note=(note or None),
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("failed to write attendance attempt")


def _reject(code, student, session, http=403, **log_kwargs):
    _log(student, session, REJECTED, code, **log_kwargs)
    return MarkResult(
        success=False,
        error=code,
        message=MESSAGES.get(code, "Attendance could not be marked."),
        status_code=http,
    )


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mark_attendance(student, session_id, payload, source_ip, device_hash):
    """Run the full chain and record attendance if every layer passes.

    ``payload`` carries only what the client can legitimately supply:
    session id, token, latitude, longitude, accuracy. The device identity
    comes from the signed cookie and the IP from the connection -- both
    are read by the caller, not taken from the body.
    """
    cfg = current_app.config

    lat = _float(payload.get("latitude"))
    lon = _float(payload.get("longitude"))
    accuracy = _float(payload.get("accuracy"))

    def reject(code, http=403, **extra):
        return _reject(
            code, student, session, http,
            lat=lat, lon=lon, accuracy=accuracy,
            device_hash=device_hash, ip=source_ip, **extra,
        )

    # --- Session exists ------------------------------------------------
    session = db.session.get(AttendanceSession, session_id)
    if session is None:
        return _reject(
            "SESSION_NOT_FOUND", student, None, 404,
            lat=lat, lon=lon, accuracy=accuracy,
            device_hash=device_hash, ip=source_ip,
        )

    # --- Layer 1: the teacher gate -------------------------------------
    # Nothing below this line is reachable until a teacher opens the
    # window. expire_if_due also closes a session whose timer ran out
    # while nobody was looking.
    expire_if_due(session)

    if not session.is_window_open():
        code = "WINDOW_EXPIRED" if session.closed_at else "WINDOW_NOT_OPEN"
        if session.opened_at is None:
            code = "WINDOW_NOT_OPEN"
        return reject(code)

    # --- Rate limiting -------------------------------------------------
    # Without this, a student can retry a spoofed reading until GPS noise
    # lets one through, or brute-force the short code.
    if anomaly_service.recent_attempt_count(student, session) >= cfg["MAX_ATTEMPTS_PER_SESSION"]:
        return reject("RATE_LIMITED", http=429)

    # --- Layer 2: rotating token ---------------------------------------
    token, token_error = token_service.validate(session, payload.get("token"))
    if token_error:
        return reject(token_error)

    # --- Layer 3: classroom network ------------------------------------
    network_error = network_service.check(
        source_ip, session.location, enforce=cfg["ENFORCE_NETWORK_CHECK"]
    )
    if network_error:
        return reject(network_error)

    # --- Layer 4: device binding ---------------------------------------
    device, device_error = device_service.check_binding(
        student, device_hash, enforce=cfg["ENFORCE_DEVICE_BINDING"]
    )
    if device_error:
        return reject(device_error)

    # --- Layer 5: device uniqueness ------------------------------------
    reuse_error = device_service.check_unused_in_session(
        device, session.id, enforce=cfg["ENFORCE_DEVICE_BINDING"]
    )
    if reuse_error:
        return reject(reuse_error)

    # --- Layer 6: enrolment --------------------------------------------
    if student.class_id != session.class_id:
        return reject("NOT_ENROLLED")

    # --- Layer 7: coordinate sanity ------------------------------------
    if lat is None or lon is None or not valid_coordinates(lat, lon):
        return reject("INVALID_LOCATION", http=400)

    mock_error = anomaly_service.check_mock_flag(payload)
    if mock_error:
        return reject(mock_error)

    # --- Layers 8 and 9: accuracy and the geofence ---------------------
    # The circle is centred on wherever the teacher was standing when
    # they opened the window, falling back to the classroom's surveyed
    # coordinates. A teacher-set anchor carries its own error, which is
    # forgiven on top of the student's.
    anchor_lat, anchor_lon, anchor_accuracy, anchor_source = session.anchor()
    distance = distance_to_anchor(lat, lon, anchor_lat, anchor_lon)
    radius = session.location.radius_meters or cfg["GEOFENCE_RADIUS_METERS"]

    verdict, effective = check_geofence(
        distance,
        accuracy,
        radius=radius,
        accuracy_credit=cfg["ACCURACY_CREDIT_METERS"],
        max_accuracy=cfg["MAX_ACCURACY_METERS"],
        anchor_accuracy=anchor_accuracy,
        anchor_credit=cfg["ANCHOR_ACCURACY_CREDIT_METERS"],
    )

    if verdict == RETRY_POOR_ACCURACY:
        result = reject("POOR_ACCURACY", http=422, distance=distance)
        result.accuracy = accuracy
        result.max_accuracy = cfg["MAX_ACCURACY_METERS"]
        # Say the actual numbers. "Accuracy too low" with no figures is
        # undiagnosable -- and the usual cause is a laptop, which has no
        # GPS chip and positions itself by Wi-Fi to within kilometres.
        if accuracy is None:
            result.message = (
                "Your browser did not report a location accuracy, so the "
                "reading cannot be checked against the classroom."
            )
        else:
            result.message = (
                f"Your location is accurate to about {accuracy:,.0f} m, but "
                f"attendance needs {cfg['MAX_ACCURACY_METERS']} m or better. "
                "Phones with GPS usually manage this; laptops positioning "
                "themselves by Wi-Fi often cannot."
            )
        return result

    if verdict == OUTSIDE:
        result = _reject(
            "OUTSIDE_RADIUS", student, session, 403,
            lat=lat, lon=lon, accuracy=accuracy, distance=distance,
            device_hash=device_hash, ip=source_ip,
        )
        result.distance_meters = distance
        result.effective_meters = effective
        result.allowed_radius = radius
        return result

    assert verdict == INSIDE

    # --- Layer 10: duplicate prevention --------------------------------
    existing = Attendance.query.filter_by(
        student_id=student.id, session_id=session.id
    ).first()
    if existing is not None:
        return reject("ALREADY_MARKED", http=409, distance=distance)

    # --- Anomaly signals -----------------------------------------------
    # The signals are recorded on the attendance row either way, so the
    # teacher can still see them. FLAG_SUSPICIOUS_RECORDS only decides
    # whether the record is held as FLAGGED or counted as PRESENT.
    signals = anomaly_service.suspicious_signals(student, session, lat, lon, accuracy)
    record_status = (
        FLAGGED if (signals and cfg["FLAG_SUSPICIOUS_RECORDS"]) else PRESENT
    )

    flags = ["WINDOW_OK", "TOKEN_OK"]
    if cfg["ENFORCE_NETWORK_CHECK"]:
        flags.append("NETWORK_OK")
    if cfg["ENFORCE_DEVICE_BINDING"]:
        flags.append("DEVICE_OK")
    flags.append("GEOFENCE_OK")

    now = utcnow()
    record = Attendance(
        student_id=student.id,
        session_id=session.id,
        date=now.date(),
        time=now.time(),
        latitude=lat,
        longitude=lon,
        accuracy=accuracy,
        distance_meters=distance,
        effective_meters=effective,
        device_id=device.id if device else None,
        token_id=token.id,
        source_ip=source_ip,
        verification_flags="|".join(flags + signals),
        status=record_status,
    )
    db.session.add(record)

    try:
        db.session.commit()
    except IntegrityError:
        # Two requests raced. The unique constraints are the real
        # guarantee; this is where losing the race is turned into a
        # sensible message rather than a 500.
        db.session.rollback()
        clash = Attendance.query.filter_by(
            student_id=student.id, session_id=session.id
        ).first()
        code = "ALREADY_MARKED" if clash else "DEVICE_ALREADY_USED"
        return reject(code, http=409, distance=distance)

    _log(
        student, session, "ACCEPTED", None,
        lat=lat, lon=lon, accuracy=accuracy, distance=distance,
        device_hash=device_hash, ip=source_ip,
        note="|".join(signals) if signals else None,
    )

    message = "Attendance marked successfully"
    if signals and record_status == FLAGGED:
        message += " (flagged for teacher review)"

    return MarkResult(
        success=True,
        message=message,
        distance_meters=distance,
        effective_meters=effective,
        allowed_radius=radius,
        attendance_id=record.id,
        record_status=record_status,
        flags=signals,
    )


def override(session, student, teacher_id, present=True, note=None):
    """Teacher marks a student by hand.

    The path for the flat battery, the broken Wi-Fi, and the student
    whose flagged record turned out to be legitimate. Always audited.
    """
    record = Attendance.query.filter_by(
        student_id=student.id, session_id=session.id
    ).first()

    now = utcnow()
    if record is None:
        record = Attendance(
            student_id=student.id,
            session_id=session.id,
            date=now.date(),
            time=now.time(),
            verification_flags="MANUAL_OVERRIDE",
        )
        db.session.add(record)

    record.status = PRESENT if present else REJECTED
    record.is_override = True
    record.override_by = teacher_id
    record.override_note = (note or "")[:255] or None

    db.session.commit()
    _log(student, session, "OVERRIDE", None, note=note)
    return record


def session_roster(session):
    """Marked students plus the attempts that failed, for the live panel."""
    marked = (
        Attendance.query.filter_by(session_id=session.id)
        .order_by(Attendance.created_at.asc())
        .all()
    )
    marked_ids = {a.student_id for a in marked}

    failures = (
        AttendanceAttempt.query.filter(
            AttendanceAttempt.session_id == session.id,
            AttendanceAttempt.result == REJECTED,
        )
        .order_by(AttendanceAttempt.attempted_at.desc())
        .limit(50)
        .all()
    )

    return {
        "marked": marked,
        "marked_ids": marked_ids,
        "failures": failures,
    }


def attendance_percentage(student):
    """Per-subject and overall attendance for a student."""
    records = Attendance.query.filter_by(student_id=student.id).all()
    present_by_subject = {}
    for record in records:
        if record.status == REJECTED:
            continue
        subject = record.session.subject
        present_by_subject.setdefault(subject.name, 0)
        present_by_subject[subject.name] += 1

    totals = {}
    sessions = AttendanceSession.query.filter_by(class_id=student.class_id).all()
    for session in sessions:
        if session.opened_at is None:
            continue  # never opened, so it never counted against anyone
        totals.setdefault(session.subject.name, 0)
        totals[session.subject.name] += 1

    rows = []
    total_present = 0
    total_held = 0
    for subject, held in sorted(totals.items()):
        present = present_by_subject.get(subject, 0)
        total_present += present
        total_held += held
        rows.append(
            {
                "subject": subject,
                "present": present,
                "total": held,
                "percentage": round(100.0 * present / held, 2) if held else 0.0,
            }
        )

    overall = round(100.0 * total_present / total_held, 2) if total_held else 0.0
    return rows, overall


def today():
    return date_cls.today()

"""Heuristics for spotting faked location readings.

These are heuristics, not proofs. They raise a record to FLAGGED for a
human to judge -- they never silently discard attendance. A student with
an unusual but honest reading should not lose a class they attended.
"""

from datetime import timedelta

from models.attendance import Attendance, AttendanceAttempt
from services.geolocation import haversine_meters
from util import utcnow

# Faster than a person can move indoors, allowing for GPS jitter.
IMPOSSIBLE_SPEED_MPS = 40.0


def check_mock_flag(payload):
    """Reject a reading the device itself admits is synthetic.

    Only the native app can set this: Android exposes
    ``Location.isFromMockProvider()``, browsers expose nothing
    equivalent. Absent means unknown, not clean.
    """
    value = payload.get("is_mock")
    if value is True or str(value).strip().lower() in ("true", "1", "yes"):
        return "INVALID_LOCATION"
    return None


def suspicious_signals(student, session, lat, lon, accuracy):
    """Collect reasons this reading looks synthetic.

    Returns a list of short strings; empty means nothing stood out.
    """
    signals = []
    anchor_lat, anchor_lon, _, _ = session.anchor()

    # Two independent fixes never agree to seven decimal places. Landing
    # exactly on the geofence centre means the number was copied, not
    # measured.
    if abs(lat - anchor_lat) < 1e-7 and abs(lon - anchor_lon) < 1e-7:
        signals.append("EXACT_CLASSROOM_MATCH")

    # Spoofing apps often emit a fixed accuracy. A suspiciously perfect
    # reading indoors is odd in itself.
    if accuracy is not None and 0 < accuracy < 1.0:
        signals.append("IMPLAUSIBLE_ACCURACY")

    if _impossible_travel(student, lat, lon):
        signals.append("IMPOSSIBLE_TRAVEL")

    return signals


def _impossible_travel(student, lat, lon, window_minutes=30):
    """Did this account just report a position it could not have reached?"""
    since = utcnow() - timedelta(minutes=window_minutes)

    previous = (
        Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.created_at >= since,
            Attendance.latitude.isnot(None),
        )
        .order_by(Attendance.created_at.desc())
        .first()
    )
    if previous is None:
        return False

    elapsed = (utcnow() - previous.created_at).total_seconds()
    if elapsed <= 0:
        return False

    distance = haversine_meters(previous.latitude, previous.longitude, lat, lon)
    # Ignore trivial hops; GPS jitter alone can produce tens of metres.
    if distance < 500:
        return False

    return (distance / elapsed) > IMPOSSIBLE_SPEED_MPS


def recent_attempt_count(student, session, minutes=5):
    """Attempts by this student against this session, for rate limiting."""
    since = utcnow() - timedelta(minutes=minutes)
    return AttendanceAttempt.query.filter(
        AttendanceAttempt.student_id == student.id,
        AttendanceAttempt.session_id == session.id,
        AttendanceAttempt.attempted_at >= since,
    ).count()

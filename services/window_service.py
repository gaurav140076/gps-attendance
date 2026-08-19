"""The teacher-controlled attendance window.

SCHEDULED -> ACTIVE -> CLOSED, and CLOSED is terminal. Reopening
requires a new session, so a closed window can never be quietly reopened
to backfill attendance.
"""

from datetime import timedelta

from extensions import db
from models.session import ACTIVE, CLOSED, SCHEDULED, AttendanceSession
from services.geolocation import valid_coordinates
from util import utcnow


class WindowError(Exception):
    """Raised when a window transition is not allowed."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def set_anchor(session, latitude, longitude, accuracy, max_anchor_accuracy):
    """Centre the geofence on the teacher's current position.

    Returns ``(applied, note)``. When the fix is missing or too vague the
    anchor is refused and the classroom's saved coordinates stand -- a
    circle centred on a bad fix is worse than one centred on a surveyed
    point, because it silently moves the classroom.
    """
    if latitude is None or longitude is None:
        return False, "NO_FIX"

    if not valid_coordinates(latitude, longitude):
        return False, "INVALID_FIX"

    if accuracy is None:
        return False, "NO_ACCURACY"

    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return False, "NO_ACCURACY"

    if accuracy <= 0 or accuracy > max_anchor_accuracy:
        return False, "POOR_ACCURACY"

    session.anchor_latitude = float(latitude)
    session.anchor_longitude = float(longitude)
    session.anchor_accuracy = accuracy
    session.anchor_source = "TEACHER"
    return True, None


def open_window(session, window_seconds, max_window_seconds,
                anchor=None, max_anchor_accuracy=30):
    """Turn attendance on. This is the switch the whole system hangs on.

    ``anchor`` is the teacher's own position, as
    ``{"latitude", "longitude", "accuracy"}``. When it is usable the
    geofence is centred there; otherwise the classroom's saved
    coordinates are used and the caller is told why.
    """
    if session.status == ACTIVE:
        raise WindowError("ALREADY_OPEN", "This window is already open.")
    if session.status == CLOSED:
        raise WindowError(
            "SESSION_CLOSED",
            "This session is closed. Create a new session to take attendance again.",
        )

    try:
        window_seconds = int(window_seconds)
    except (TypeError, ValueError):
        raise WindowError("INVALID_WINDOW", "Window length must be a number.")

    if window_seconds < 10:
        raise WindowError("INVALID_WINDOW", "Window must be at least 10 seconds.")

    # Clamp rather than reject: the ceiling exists because a long window
    # hands back the time budget that makes proxy impractical.
    window_seconds = min(window_seconds, max_window_seconds)

    anchor_note = "NOT_REQUESTED"
    if anchor:
        applied, anchor_note = set_anchor(
            session,
            anchor.get("latitude"),
            anchor.get("longitude"),
            anchor.get("accuracy"),
            max_anchor_accuracy,
        )
        if applied:
            anchor_note = None

    now = utcnow()
    session.status = ACTIVE
    session.opened_at = now
    session.closes_at = now + timedelta(seconds=window_seconds)
    session.window_seconds = window_seconds
    db.session.commit()
    return session, anchor_note


def close_window(session):
    """Shut the window and invalidate every outstanding token."""
    if session.status == CLOSED:
        return session

    now = utcnow()
    session.status = CLOSED
    session.closed_at = now
    if session.closes_at is None or session.closes_at > now:
        session.closes_at = now

    # Expire tokens immediately so a code photographed seconds before the
    # teacher pressed Close cannot still be redeemed.
    for token in session.tokens:
        if token.expires_at > now:
            token.expires_at = now

    db.session.commit()
    return session


def expire_if_due(session):
    """Auto-close a session whose window has run out.

    Called on every read of session state, which is what stops a session
    left ACTIVE by a crashed process from staying open forever.
    """
    if session.status != ACTIVE:
        return session
    if session.closes_at is not None and utcnow() > session.closes_at:
        close_window(session)
    return session


def expire_all_due():
    """Sweep every overdue session. Cheap enough to call per request."""
    now = utcnow()
    overdue = AttendanceSession.query.filter(
        AttendanceSession.status == ACTIVE,
        AttendanceSession.closes_at.isnot(None),
        AttendanceSession.closes_at < now,
    ).all()
    for session in overdue:
        close_window(session)
    return len(overdue)


def open_sessions_for_class(class_id):
    """Sessions a student in this class may currently mark against."""
    expire_all_due()
    return (
        AttendanceSession.query.filter(
            AttendanceSession.class_id == class_id,
            AttendanceSession.status == ACTIVE,
        )
        .order_by(AttendanceSession.opened_at.desc())
        .all()
    )


__all__ = [
    "ACTIVE",
    "CLOSED",
    "SCHEDULED",
    "WindowError",
    "close_window",
    "expire_all_due",
    "expire_if_due",
    "open_sessions_for_class",
    "open_window",
    "set_anchor",
]

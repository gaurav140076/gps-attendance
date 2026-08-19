"""Rotating one-time tokens for the teacher's QR code.

The token is what a student must read off the classroom screen. Its whole
value is that it dies in seconds: a code photographed and messaged to an
absent friend is worthless by the time it arrives.
"""

import secrets
from datetime import timedelta

from extensions import db
from models.session import SessionToken
from util import utcnow

# Ambiguous characters removed, since students type this one by hand.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _display_code(length=6):
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def current_token(session):
    """The token to display right now, minting a new one when due.

    Rotation is driven by the age of the newest token rather than by a
    background job, so the schedule holds without a scheduler.
    """
    if not session.is_window_open():
        return None

    now = utcnow()
    newest = (
        SessionToken.query.filter_by(session_id=session.id)
        .order_by(SessionToken.issued_at.desc())
        .first()
    )

    if newest is not None:
        age = (now - newest.issued_at).total_seconds()
        if age < session.token_rotation_seconds:
            return newest

    return issue_token(session)


def issue_token(session):
    """Mint a fresh token.

    The value is cryptographically random -- never a hash of the session
    id or the clock, which an absent student could compute.
    """
    now = utcnow()
    token = SessionToken(
        session_id=session.id,
        token=secrets.token_urlsafe(32),
        display_code=_display_code(),
        issued_at=now,
        expires_at=now + timedelta(seconds=session.token_ttl_seconds),
    )
    db.session.add(token)
    db.session.commit()
    return token


def validate(session, submitted):
    """Look up a submitted token or short code for this session.

    Returns ``(token, error_code)``; exactly one is set. Both forms are
    accepted because a camera that will not focus should not cost an
    honest student their attendance.
    """
    if not submitted or not str(submitted).strip():
        return None, "TOKEN_MISSING"

    submitted = str(submitted).strip()
    now = utcnow()

    row = SessionToken.query.filter_by(token=submitted).first()
    if row is None:
        row = SessionToken.query.filter_by(
            session_id=session.id, display_code=submitted.upper()
        ).order_by(SessionToken.issued_at.desc()).first()

    if row is None:
        return None, "TOKEN_INVALID"

    # A token from another session is invalid here even if it is live
    # there -- otherwise a code from the lecture next door would work.
    if row.session_id != session.id:
        return None, "TOKEN_INVALID"

    if not row.is_valid(now):
        return None, "TOKEN_EXPIRED"

    return row, None


def invalidate_all(session):
    now = utcnow()
    for token in session.tokens:
        if token.expires_at > now:
            token.expires_at = now
    db.session.commit()


def purge_expired(session):
    """Drop dead tokens once a session is finished."""
    now = utcnow()
    stale = SessionToken.query.filter(
        SessionToken.session_id == session.id, SessionToken.expires_at < now
    ).all()
    for token in stale:
        db.session.delete(token)
    db.session.commit()
    return len(stale)

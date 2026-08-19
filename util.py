"""Small helpers shared across the app."""

from datetime import datetime, timezone


def utcnow():
    """Current UTC time as a naive datetime.

    SQLite stores naive datetimes, so keeping one representation
    everywhere avoids comparing aware and naive values -- which raises
    at runtime and would break the attendance window check.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

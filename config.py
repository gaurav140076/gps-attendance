"""Configuration for the GPS Self-Attendance System.

Every value here has a security consequence. The defaults match the
numbers documented in the README; the ones that weaken the anti-proxy
guarantee are called out individually.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(name, default):
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _database_url():
    """Normalise the hosting provider's DATABASE_URL.

    Railway (like Heroku) hands out a `postgres://` URL. SQLAlchemy 2
    rejects that scheme outright, and the default `postgresql://` scheme
    resolves to psycopg2, which we do not install -- so both are pointed
    at psycopg 3 explicitly.
    """
    raw = os.getenv("DATABASE_URL", "sqlite:///attendance.db")

    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Hosted Postgres drops idle connections; without pre-ping the first
    # request after a quiet spell fails with a stale-connection error.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Create tables on boot if they are missing. Harmless and idempotent,
    # and it means a fresh deployment does not need a separate migration
    # step before it will serve a request.
    AUTO_CREATE_TABLES = _bool("AUTO_CREATE_TABLES", True)

    # --- Geofence -----------------------------------------------------
    # The configured classroom radius. Locations may override it, but
    # this is the default applied to new locations.
    GEOFENCE_RADIUS_METERS = _int("GEOFENCE_RADIUS_METERS", 10)

    # How much of a reading's own stated error we forgive. Without this,
    # a 10 m radius rejects students who are genuinely in the room,
    # because indoor GPS error is routinely larger than the radius.
    ACCURACY_CREDIT_METERS = _int("ACCURACY_CREDIT_METERS", 35)

    # Readings vaguer than this tell us nothing useful against a 10 m
    # radius, so we ask for a retry rather than guessing.
    MAX_ACCURACY_METERS = _int("MAX_ACCURACY_METERS", 50)

    # --- Teacher-anchored geofence ------------------------------------
    # The circle is centred on wherever the teacher was standing when
    # they opened the window, rather than on a surveyed coordinate. The
    # teacher is in the room, so this is usually more accurate than a map
    # pin -- and it removes the surveying step entirely.
    ANCHOR_ON_TEACHER_LOCATION = _bool("ANCHOR_ON_TEACHER_LOCATION", True)

    # A surveyed point was assumed exact. A live fix is not, so the
    # anchor's own error has to be forgiven on top of the student's --
    # otherwise two people standing together can read 25 m apart and the
    # student is rejected for the teacher's GPS noise.
    ANCHOR_ACCURACY_CREDIT_METERS = _int("ANCHOR_ACCURACY_CREDIT_METERS", 25)

    # An anchor vaguer than this puts the circle somewhere else in the
    # building, so it is refused and the saved coordinates are used.
    MAX_ANCHOR_ACCURACY_METERS = _int("MAX_ANCHOR_ACCURACY_METERS", 30)

    # --- Teacher-controlled window ------------------------------------
    DEFAULT_WINDOW_SECONDS = _int("DEFAULT_WINDOW_SECONDS", 120)
    # Raising this weakens the strongest anti-proxy control in the
    # system: the attacker's time budget.
    MAX_WINDOW_SECONDS = _int("MAX_WINDOW_SECONDS", 300)

    # --- Rotating QR token --------------------------------------------
    # The code is displayed for 30 seconds and accepted for 35, so a
    # student who submits just as it rotates is not punished for the
    # round trip. Longer than this starts to matter: the token's whole
    # value is that a code photographed and sent to an absent friend is
    # dead before it arrives.
    TOKEN_ROTATION_SECONDS = _int("TOKEN_ROTATION_SECONDS", 30)
    TOKEN_TTL_SECONDS = _int("TOKEN_TTL_SECONDS", 35)

    # --- Anti-proxy toggles -------------------------------------------
    # These exist so the app can run on a laptop during development.
    # Both must be true in any real deployment.
    ENFORCE_NETWORK_CHECK = _bool("ENFORCE_NETWORK_CHECK", True)
    ENFORCE_DEVICE_BINDING = _bool("ENFORCE_DEVICE_BINDING", True)

    DEVICE_COOKIE_NAME = os.getenv("DEVICE_COOKIE_NAME", "att_device")
    DEVICE_COOKIE_MAX_AGE = _int("DEVICE_COOKIE_MAX_AGE", 60 * 60 * 24 * 365)

    # Number of proxies in front of the app. Leave at 0 unless you
    # control the proxy chain: trusting X-Forwarded-For blindly lets any
    # student claim to be on the classroom network.
    TRUSTED_PROXY_COUNT = _int("TRUSTED_PROXY_COUNT", 0)

    # --- Rate limiting -------------------------------------------------
    MAX_ATTEMPTS_PER_SESSION = _int("MAX_ATTEMPTS_PER_SESSION", 10)

    # --- Anomaly handling ----------------------------------------------
    # When a reading trips a mock-location heuristic, record it as
    # PRESENT rather than FLAGGED. The signals are still written to the
    # record and shown to the teacher either way -- this only decides
    # whether the student sees a clean "present".
    #
    # Off by default because the heuristics fire on honest cases too: two
    # windows on one laptop report byte-identical coordinates, which
    # looks synthetic but is not. Set true to have suspicious records
    # held as FLAGGED for review instead.
    FLAG_SUSPICIOUS_RECORDS = _bool("FLAG_SUSPICIOUS_RECORDS", False)

    # --- Cookies -------------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enable in deployment (requires HTTPS, which geolocation needs anyway).
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)


class TestConfig(Config):
    """Fixed configuration for the test suite.

    Every security-relevant value is pinned rather than inherited. The
    base class reads them from the environment, so without this a
    developer's local .env -- for instance one with relaxed accuracy
    limits so the app can be demoed on a laptop -- would silently change
    what the tests assert and could turn a real regression green.
    """

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False
    AUTO_CREATE_TABLES = False

    GEOFENCE_RADIUS_METERS = 10
    ACCURACY_CREDIT_METERS = 35
    MAX_ACCURACY_METERS = 50

    ANCHOR_ON_TEACHER_LOCATION = True
    ANCHOR_ACCURACY_CREDIT_METERS = 25
    MAX_ANCHOR_ACCURACY_METERS = 30

    DEFAULT_WINDOW_SECONDS = 120
    MAX_WINDOW_SECONDS = 300

    TOKEN_ROTATION_SECONDS = 30
    TOKEN_TTL_SECONDS = 35

    ENFORCE_NETWORK_CHECK = True
    ENFORCE_DEVICE_BINDING = True
    TRUSTED_PROXY_COUNT = 0
    MAX_ATTEMPTS_PER_SESSION = 10
    FLAG_SUSPICIOUS_RECORDS = False

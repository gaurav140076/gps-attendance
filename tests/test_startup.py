"""Application startup.

Covers the failure that took the first Railway deployment down: gunicorn
boots several workers, every one of them calls create_app(), and their
create_all() calls raced each other into a duplicate-key error on the
Postgres system catalogue.
"""

import os
import tempfile

import pytest

from app import create_app
from config import Config, TestConfig, _database_url
from extensions import db
from models.people import Admin


@pytest.fixture
def sqlite_file():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _config_for(path):
    class FileConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path}"
        AUTO_CREATE_TABLES = True

    return FileConfig


def test_startup_creates_the_schema(sqlite_file):
    app = create_app(_config_for(sqlite_file))
    with app.app_context():
        assert Admin.query.count() == 0  # table exists and is queryable


def test_repeated_startup_is_idempotent(sqlite_file):
    """Every worker runs this, and a redeploy runs it again.

    It must be safe against a database that already has the schema, and
    it must not disturb existing rows.
    """
    config = _config_for(sqlite_file)

    app = create_app(config)
    with app.app_context():
        admin = Admin(name="Existing", email="existing@college.edu")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

    for _ in range(3):
        again = create_app(config)
        with again.app_context():
            assert Admin.query.count() == 1
            assert Admin.query.first().name == "Existing"


def test_auto_create_can_be_switched_off(sqlite_file):
    class NoCreate(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{sqlite_file}"
        AUTO_CREATE_TABLES = False

    app = create_app(NoCreate)
    with app.app_context():
        from sqlalchemy import inspect

        assert inspect(db.engine).get_table_names() == []


# --- The DATABASE_URL rewrite the host depends on ------------------------

@pytest.mark.parametrize(
    "given,expected",
    [
        # What Railway and Heroku actually hand out. SQLAlchemy 2 rejects
        # this scheme outright.
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        # Valid, but resolves to psycopg2, which is not installed.
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        # Already explicit; must be left alone.
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///attendance.db", "sqlite:///attendance.db"),
    ],
)
def test_database_url_is_normalised(monkeypatch, given, expected):
    monkeypatch.setenv("DATABASE_URL", given)
    assert _database_url() == expected


def test_rewritten_url_resolves_to_psycopg3(monkeypatch):
    from sqlalchemy.engine import make_url

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db")
    url = make_url(_database_url())

    assert url.drivername == "postgresql+psycopg"
    assert url.get_dialect().__name__ == "PGDialect_psycopg"


def test_default_is_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _database_url().startswith("sqlite:///")


def test_production_pooling_is_configured():
    """Hosted Postgres drops idle connections; without pre-ping the first
    request after a quiet spell fails."""
    assert Config.SQLALCHEMY_ENGINE_OPTIONS.get("pool_pre_ping") is True

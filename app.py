"""Application factory and CLI entry point."""

import os

import click
from flask import Flask, jsonify, request

from config import Config
from extensions import db


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    # Importing the package registers every model with the metadata, so
    # create_all() sees the full schema.
    import models  # noqa: F401

    from routes import admin, attendance, auth, pages, student, teacher

    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(attendance.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(teacher.bp)
    app.register_blueprint(admin.bp)

    _register_errors(app)
    _register_cli(app)
    _register_context(app)
    _warn_on_weak_config(app)

    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            db.create_all()

    return app


def _register_context(app):
    """Expose the logged-in account to every template.

    Templates ask for ``current_user`` rather than reaching into Flask's
    ``session``, which a view variable can shadow.
    """

    @app.context_processor
    def inject_user():
        from services.auth_service import current_user

        return {"current_user": current_user()}


def _register_errors(app):
    """API paths get JSON; page paths keep Flask's HTML defaults."""

    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(400)
    def bad_request(_):
        if wants_json():
            return jsonify({"success": False, "error": "BAD_REQUEST"}), 400
        return "Bad request", 400

    @app.errorhandler(403)
    def forbidden(_):
        if wants_json():
            return jsonify({"success": False, "error": "FORBIDDEN"}), 403
        return "Forbidden", 403

    @app.errorhandler(404)
    def not_found(_):
        if wants_json():
            return jsonify({"success": False, "error": "NOT_FOUND"}), 404
        return "Not found", 404

    @app.errorhandler(500)
    def server_error(exc):
        app.logger.exception("unhandled error: %s", exc)
        db.session.rollback()
        if wants_json():
            return jsonify({"success": False, "error": "SERVER_ERROR"}), 500
        return "Server error", 500


def _warn_on_weak_config(app):
    """Say plainly when the anti-proxy layers are switched off.

    A silently weakened deployment is worse than an obviously weakened
    one, because nobody knows to compensate for it.
    """
    if app.config.get("TESTING"):
        return

    if app.config["SECRET_KEY"] == "dev-only-change-me":
        app.logger.warning(
            "SECRET_KEY is the default. Set it in .env before deploying: "
            "device cookies are signed with it."
        )
    if not app.config["ENFORCE_NETWORK_CHECK"]:
        app.logger.warning(
            "ENFORCE_NETWORK_CHECK is off. Students can mark attendance "
            "from any network."
        )
    if not app.config["ENFORCE_DEVICE_BINDING"]:
        app.logger.warning(
            "ENFORCE_DEVICE_BINDING is off. One phone can mark attendance "
            "for the whole class."
        )

    # Relaxed accuracy limits are the usual way to get a laptop demo
    # working, and the usual thing somebody forgets to undo.
    if app.config["MAX_ACCURACY_METERS"] > 100:
        app.logger.warning(
            "MAX_ACCURACY_METERS is %s (production: 50). Readings this vague "
            "cannot place a student in a room -- fine for a desktop demo, "
            "not for a classroom.",
            app.config["MAX_ACCURACY_METERS"],
        )
    if app.config["MAX_ANCHOR_ACCURACY_METERS"] > 100:
        app.logger.warning(
            "MAX_ANCHOR_ACCURACY_METERS is %s (production: 30). The geofence "
            "can be centred on a fix that is kilometres out.",
            app.config["MAX_ANCHOR_ACCURACY_METERS"],
        )

    # Behind a hosting proxy every request arrives from the proxy, so
    # without this the classroom network check compares the wrong address
    # and refuses everyone -- or, worse, matches everyone.
    if app.config["ENFORCE_NETWORK_CHECK"] and app.config["TRUSTED_PROXY_COUNT"] == 0:
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT"):
            app.logger.warning(
                "Running behind a proxy with TRUSTED_PROXY_COUNT=0. The "
                "classroom network check will see the proxy's address, not "
                "the student's. Set TRUSTED_PROXY_COUNT=1."
            )


def _register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed")
    def seed_command():
        """Load demo data."""
        from seed import seed

        seed()
        click.echo("Demo data loaded.")

    @app.cli.command("upgrade-db")
    def upgrade_db():
        """Add columns introduced after the database was created.

        A real deployment would use Alembic. This exists so an existing
        demo database survives the schema change instead of having to be
        deleted and re-seeded.
        """
        from sqlalchemy import inspect, text

        added = 0
        inspector = inspect(db.engine)

        wanted = {
            "attendance_sessions": {
                "anchor_latitude": "FLOAT",
                "anchor_longitude": "FLOAT",
                "anchor_accuracy": "FLOAT",
                "anchor_source": "VARCHAR(20) NOT NULL DEFAULT 'LOCATION'",
            },
            # No UNIQUE here: SQLite cannot add a unique column via ALTER
            # TABLE. The constraint applies to databases built by
            # create_all(); uniqueness is also checked in the admin route,
            # which is what an operator actually goes through.
            "teachers": {
                "teacher_id": "VARCHAR(40)",
            },
        }

        for table, columns in wanted.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in existing:
                    continue
                db.session.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                )
                added += 1
                click.echo(f"  added {table}.{name}")

        db.session.commit()
        click.echo(f"Done. {added} column(s) added.")

    @app.cli.command("expire-windows")
    def expire_windows():
        """Close any session whose window has run out."""
        from services.window_service import expire_all_due

        count = expire_all_due()
        click.echo(f"Closed {count} overdue session(s).")


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # Geolocation needs a secure context: localhost counts, so plain HTTP
    # is fine for development. A real deployment needs HTTPS.
    app.run(host="0.0.0.0", port=5000, debug=True)

"""Authentication and role-based access control."""

from functools import wraps

from flask import jsonify, redirect, request, session, url_for

from extensions import db
from models.people import Admin, Student, Teacher

_MODELS = {"STUDENT": Student, "TEACHER": Teacher, "ADMIN": Admin}


def login(user):
    session.clear()
    session["user_id"] = user.id
    session["role"] = user.role


def logout():
    session.clear()


def current_user():
    """The logged-in account, or None.

    Deliberately not cached on ``g``: ``g`` belongs to the *application*
    context, and Flask reuses an existing one rather than pushing a fresh
    context per request. Caching there survives a logout and makes the
    next request answer as the previous user. Repeated calls are cheap
    anyway -- a primary-key lookup is served from the identity map.
    """
    role = session.get("role")
    user_id = session.get("user_id")
    model = _MODELS.get(role)

    if not model or not user_id:
        return None
    return db.session.get(model, user_id)


def authenticate(role, email, password):
    model = _MODELS.get(role)
    if model is None:
        return None

    user = model.query.filter_by(email=(email or "").strip().lower()).first()
    if user is None or not user.check_password(password or ""):
        return None
    if getattr(user, "is_active", True) is False:
        return None
    return user


def _unauthorized():
    """JSON for API callers, a redirect for browsers."""
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "UNAUTHENTICATED"}), 401
    return redirect(url_for("pages.login", next=request.path))


def _forbidden():
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "FORBIDDEN"}), 403
    return redirect(url_for("pages.login"))


def role_required(*roles):
    """Restrict a view to one or more roles.

    A student must never reach a teacher or admin endpoint, so this is
    applied to every non-public route rather than relying on the UI not
    to link there.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return _unauthorized()
            if roles and user.role not in roles:
                return _forbidden()
            return view(*args, **kwargs)

        return wrapper

    return decorator


student_required = role_required("STUDENT")
teacher_required = role_required("TEACHER")
admin_required = role_required("ADMIN")
staff_required = role_required("TEACHER", "ADMIN")

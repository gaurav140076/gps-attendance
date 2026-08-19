"""Registration, login and logout."""

from flask import Blueprint, jsonify, make_response, redirect, request, url_for

from extensions import db
from models.academic import ClassGroup
from models.people import Student
from routes.helpers import ensure_device_cookie, payload
from services import auth_service

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    data = payload()

    name = (data.get("name") or "").strip()
    roll_no = (data.get("roll_no") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    class_id = data.get("class_id")

    if not (name and roll_no and email and password):
        return jsonify(
            {"success": False, "error": "MISSING_FIELDS",
             "message": "Name, roll number, email and password are required."}
        ), 400

    if len(password) < 8:
        return jsonify(
            {"success": False, "error": "WEAK_PASSWORD",
             "message": "Password must be at least 8 characters."}
        ), 400

    if Student.query.filter_by(email=email).first():
        return jsonify(
            {"success": False, "error": "EMAIL_TAKEN",
             "message": "An account with that email already exists."}
        ), 409

    if Student.query.filter_by(roll_no=roll_no).first():
        return jsonify(
            {"success": False, "error": "ROLL_TAKEN",
             "message": "An account with that roll number already exists."}
        ), 409

    student = Student(name=name, roll_no=roll_no, email=email)
    student.set_password(password)

    if class_id:
        group = db.session.get(ClassGroup, int(class_id))
        if group is not None:
            student.class_id = group.id
            student.department_id = group.department_id

    db.session.add(student)
    db.session.commit()

    auth_service.login(student)
    response = make_response(
        jsonify({"success": True, "message": "Account created.",
                 "redirect": url_for("pages.student_dashboard")})
    )
    response, _ = ensure_device_cookie(response)
    return response


@bp.post("/login")
def login():
    data = payload()
    role = (data.get("role") or "STUDENT").strip().upper()

    user = auth_service.authenticate(role, data.get("email"), data.get("password"))
    if user is None:
        # One message for both wrong-email and wrong-password, so the
        # response does not confirm which accounts exist.
        message = "Incorrect email or password."
        if request.path.startswith("/api/") or request.is_json:
            return jsonify({"success": False, "error": "BAD_CREDENTIALS",
                            "message": message}), 401
        return redirect(url_for("pages.login", error=message))

    auth_service.login(user)

    targets = {
        "STUDENT": "pages.student_dashboard",
        "TEACHER": "pages.teacher_dashboard",
        "ADMIN": "pages.admin_dashboard",
    }
    destination = url_for(targets[user.role])

    if request.is_json:
        response = make_response(
            jsonify({"success": True, "role": user.role, "redirect": destination})
        )
    else:
        response = make_response(redirect(destination))

    if user.role == "STUDENT":
        response, _ = ensure_device_cookie(response)
    return response


@bp.post("/logout")
@bp.get("/logout")
def logout():
    auth_service.logout()
    if request.is_json:
        return jsonify({"success": True})
    return redirect(url_for("pages.login"))

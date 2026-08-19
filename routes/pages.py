"""Server-rendered pages. The JSON APIs do the work; these are the shell."""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from extensions import db
from models.academic import ClassGroup, Department, Subject
from models.location import Location
from models.people import Student
from models.session import AttendanceSession
from services import attendance_service, window_service
from services.auth_service import (
    admin_required,
    current_user,
    student_required,
    teacher_required,
)
from models.attendance import Attendance

bp = Blueprint("pages", __name__)


@bp.get("/")
def index():
    user = current_user()
    if user is None:
        return redirect(url_for("pages.login"))
    return redirect(
        url_for(
            {
                "STUDENT": "pages.student_dashboard",
                "TEACHER": "pages.teacher_dashboard",
                "ADMIN": "pages.admin_dashboard",
            }[user.role]
        )
    )


@bp.get("/login")
def login():
    return render_template(
        "login.html",
        error=request.args.get("error"),
        classes=ClassGroup.query.order_by(ClassGroup.name).all(),
    )


# --- Student -----------------------------------------------------------

@bp.get("/student/dashboard")
@student_required
def student_dashboard():
    student = current_user()
    window_service.expire_all_due()
    return render_template(
        "student/dashboard.html",
        student=student,
        device=student.active_device(),
    )


@bp.get("/student/attendance")
@student_required
def student_attendance():
    student = current_user()
    return render_template("student/attendance.html", student=student)


@bp.get("/student/history")
@student_required
def student_history():
    student = current_user()
    records = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.date.desc(), Attendance.time.desc())
        .all()
    )
    rows, overall = attendance_service.attendance_percentage(student)
    return render_template(
        "student/history.html",
        student=student,
        records=records,
        by_subject=rows,
        overall=overall,
    )


# --- Teacher -----------------------------------------------------------

@bp.get("/teacher/dashboard")
@teacher_required
def teacher_dashboard():
    teacher = current_user()
    window_service.expire_all_due()
    sessions = (
        AttendanceSession.query.filter_by(teacher_id=teacher.id)
        .order_by(AttendanceSession.created_at.desc())
        .limit(25)
        .all()
    )
    return render_template(
        "teacher/dashboard.html",
        teacher=teacher,
        sessions=sessions,
        classes=ClassGroup.query.order_by(ClassGroup.name).all(),
        subjects=Subject.query.order_by(Subject.name).all(),
        locations=Location.query.order_by(Location.name).all(),
    )


@bp.get("/teacher/sessions/<int:session_id>")
@teacher_required
def teacher_session(session_id):
    session = db.session.get(AttendanceSession, session_id)
    if session is None:
        abort(404)
    if session.teacher_id != current_user().id:
        abort(403)

    window_service.expire_if_due(session)
    # Named att_session in the template: `session` there is Flask's.
    return render_template("teacher/session.html", att_session=session)


# --- Admin -------------------------------------------------------------

@bp.get("/admin/dashboard")
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html", admin=current_user())


@bp.get("/admin/students")
@admin_required
def admin_students():
    return render_template(
        "admin/students.html",
        classes=ClassGroup.query.order_by(ClassGroup.name).all(),
        departments=Department.query.order_by(Department.name).all(),
    )


@bp.get("/admin/teachers")
@admin_required
def admin_teachers():
    return render_template(
        "admin/teachers.html",
        departments=Department.query.order_by(Department.name).all(),
    )


@bp.get("/admin/academic")
@admin_required
def admin_academic():
    return render_template(
        "admin/academic.html",
        departments=Department.query.order_by(Department.name).all(),
    )


@bp.get("/admin/locations")
@admin_required
def admin_locations():
    return render_template(
        "admin/locations.html",
        locations=Location.query.order_by(Location.name).all(),
    )


@bp.get("/admin/devices")
@admin_required
def admin_devices():
    return render_template("admin/devices.html")


@bp.get("/admin/reports")
@admin_required
def admin_reports():
    return render_template(
        "admin/reports.html",
        students=Student.query.order_by(Student.roll_no).all(),
    )


@bp.get("/admin/attempts")
@admin_required
def admin_attempts():
    return render_template("admin/attempts.html")

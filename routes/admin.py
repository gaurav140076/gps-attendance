"""Admin APIs: users, locations, networks, devices, reports."""

from flask import Blueprint, Response, abort, jsonify

from extensions import db
from models.academic import ClassGroup, Department, Subject
from models.attendance import Attendance, AttendanceAttempt
from models.device import Device
from models.location import Location
from models.people import Student, Teacher
from models.session import AttendanceSession
from routes.helpers import payload
from services import report_service
from services.auth_service import admin_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# --- Students ----------------------------------------------------------

@bp.get("/students")
@admin_required
def list_students():
    students = Student.query.order_by(Student.roll_no.asc()).all()
    return jsonify(
        {
            "success": True,
            "students": [
                {
                    "id": s.id,
                    "name": s.name,
                    "roll_no": s.roll_no,
                    "email": s.email,
                    "class": s.class_group.name if s.class_group else None,
                    "active": s.is_active,
                    "device_registered": s.active_device() is not None,
                }
                for s in students
            ],
        }
    )


@bp.post("/students")
@admin_required
def create_student():
    data = payload()
    required = ("name", "roll_no", "email", "password")
    if not all((data.get(f) or "").strip() for f in required):
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400

    email = data["email"].strip().lower()
    if Student.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "EMAIL_TAKEN"}), 409

    student = Student(
        name=data["name"].strip(),
        roll_no=data["roll_no"].strip(),
        email=email,
        class_id=int(data["class_id"]) if data.get("class_id") else None,
        department_id=int(data["department_id"]) if data.get("department_id") else None,
    )
    student.set_password(data["password"])
    db.session.add(student)
    db.session.commit()
    return jsonify({"success": True, "id": student.id}), 201


@bp.put("/students/<int:student_id>")
@admin_required
def update_student(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)

    data = payload()
    for field in ("name", "roll_no", "email"):
        if data.get(field):
            setattr(student, field, data[field].strip())
    if data.get("class_id"):
        student.class_id = int(data["class_id"])
    if data.get("password"):
        student.set_password(data["password"])
    if "is_active" in data:
        student.is_active = str(data["is_active"]).lower() not in ("false", "0", "no")

    db.session.commit()
    return jsonify({"success": True})


@bp.delete("/students/<int:student_id>")
@admin_required
def deactivate_student(student_id):
    """Deactivate rather than delete, so attendance history survives."""
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)
    student.is_active = False
    db.session.commit()
    return jsonify({"success": True, "message": "Student deactivated."})


# --- Teachers ----------------------------------------------------------

@bp.get("/teachers")
@admin_required
def list_teachers():
    teachers = Teacher.query.order_by(Teacher.name.asc()).all()
    return jsonify(
        {
            "success": True,
            "teachers": [
                {
                    "id": t.id,
                    "teacher_id": t.teacher_id,
                    "name": t.name,
                    "email": t.email,
                    "department": t.department_id,
                }
                for t in teachers
            ],
        }
    )


@bp.post("/teachers")
@admin_required
def create_teacher():
    data = payload()
    if not all((data.get(f) or "").strip() for f in ("name", "email", "password")):
        return jsonify(
            {"success": False, "error": "MISSING_FIELDS",
             "message": "Name, email and password are required."}
        ), 400

    email = data["email"].strip().lower()
    if Teacher.query.filter_by(email=email).first():
        return jsonify(
            {"success": False, "error": "EMAIL_TAKEN",
             "message": f"{email} already has an account."}
        ), 409

    # The staff code is typed by hand, so it has to be checked rather
    # than trusted: two teachers sharing one code would make every
    # report that groups by it wrong.
    teacher_id = (data.get("teacher_id") or "").strip() or None
    if teacher_id and Teacher.query.filter_by(teacher_id=teacher_id).first():
        return jsonify(
            {"success": False, "error": "TEACHER_ID_TAKEN",
             "message": f"Teacher ID {teacher_id} is already assigned."}
        ), 409

    teacher = Teacher(
        teacher_id=teacher_id,
        name=data["name"].strip(),
        email=email,
        department_id=int(data["department_id"]) if data.get("department_id") else None,
    )
    teacher.set_password(data["password"])
    db.session.add(teacher)
    db.session.commit()
    return jsonify(
        {"success": True, "id": teacher.id, "teacher_id": teacher.teacher_id}
    ), 201


@bp.put("/teachers/<int:teacher_id>")
@admin_required
def update_teacher(teacher_id):
    teacher = db.session.get(Teacher, teacher_id)
    if teacher is None:
        abort(404)

    data = payload()

    if "teacher_id" in data:
        new_code = (data.get("teacher_id") or "").strip() or None
        if new_code and new_code != teacher.teacher_id:
            clash = Teacher.query.filter_by(teacher_id=new_code).first()
            if clash is not None:
                return jsonify(
                    {"success": False, "error": "TEACHER_ID_TAKEN",
                     "message": f"Teacher ID {new_code} is already assigned "
                                f"to {clash.name}."}
                ), 409
        teacher.teacher_id = new_code

    if data.get("name"):
        teacher.name = data["name"].strip()
    if data.get("email"):
        teacher.email = data["email"].strip().lower()
    if data.get("password"):
        teacher.set_password(data["password"])
    if data.get("department_id"):
        teacher.department_id = int(data["department_id"])

    db.session.commit()
    return jsonify({"success": True})


@bp.delete("/teachers/<int:teacher_id>")
@admin_required
def delete_teacher(teacher_id):
    """Refuse if the teacher owns sessions.

    Attendance records point at those sessions; removing the teacher
    would orphan the audit trail that makes a disputed record checkable.
    """
    teacher = db.session.get(Teacher, teacher_id)
    if teacher is None:
        abort(404)

    if teacher.sessions:
        return jsonify(
            {"success": False, "error": "IN_USE",
             "message": f"{teacher.name} owns {len(teacher.sessions)} session(s). "
                        "Deleting them would break the attendance audit trail."}
        ), 409

    db.session.delete(teacher)
    db.session.commit()
    return jsonify({"success": True})


# --- Locations ---------------------------------------------------------

@bp.get("/locations")
@admin_required
def list_locations():
    locations = Location.query.order_by(Location.name.asc()).all()
    return jsonify(
        {
            "success": True,
            "locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "radius_meters": loc.radius_meters,
                    "allowed_networks": loc.allowed_networks,
                    "wifi_bssid": loc.wifi_bssid,
                }
                for loc in locations
            ],
        }
    )


def _validate_location(data, partial=False):
    """Range-check a location payload.

    At a 10 m radius a coordinate typo is not a cosmetic problem: it moves
    the classroom and rejects the whole class.
    """
    errors = {}

    if not partial or "latitude" in data:
        try:
            lat = float(data["latitude"])
            if not -90 <= lat <= 90:
                errors["latitude"] = "must be between -90 and 90"
        except (KeyError, TypeError, ValueError):
            errors["latitude"] = "required, numeric"

    if not partial or "longitude" in data:
        try:
            lon = float(data["longitude"])
            if not -180 <= lon <= 180:
                errors["longitude"] = "must be between -180 and 180"
        except (KeyError, TypeError, ValueError):
            errors["longitude"] = "required, numeric"

    if "radius_meters" in data:
        try:
            radius = int(data["radius_meters"])
            if radius < 1 or radius > 5000:
                errors["radius_meters"] = "must be between 1 and 5000"
        except (TypeError, ValueError):
            errors["radius_meters"] = "must be an integer"

    return errors


@bp.post("/locations")
@admin_required
def create_location():
    from flask import current_app

    data = payload()
    if not (data.get("name") or "").strip():
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400

    errors = _validate_location(data)
    if errors:
        return jsonify({"success": False, "error": "INVALID", "fields": errors}), 400

    location = Location(
        name=data["name"].strip(),
        latitude=float(data["latitude"]),
        longitude=float(data["longitude"]),
        radius_meters=int(
            data.get("radius_meters") or current_app.config["GEOFENCE_RADIUS_METERS"]
        ),
        allowed_networks=(data.get("allowed_networks") or "").strip(),
        wifi_bssid=(data.get("wifi_bssid") or "").strip() or None,
    )
    db.session.add(location)
    db.session.commit()
    return jsonify({"success": True, "id": location.id}), 201


@bp.put("/locations/<int:location_id>")
@admin_required
def update_location(location_id):
    location = db.session.get(Location, location_id)
    if location is None:
        abort(404)

    data = payload()
    errors = _validate_location(data, partial=True)
    if errors:
        return jsonify({"success": False, "error": "INVALID", "fields": errors}), 400

    if data.get("name"):
        location.name = data["name"].strip()
    if "latitude" in data:
        location.latitude = float(data["latitude"])
    if "longitude" in data:
        location.longitude = float(data["longitude"])
    if "radius_meters" in data:
        location.radius_meters = int(data["radius_meters"])
    if "allowed_networks" in data:
        location.allowed_networks = (data["allowed_networks"] or "").strip()
    if "wifi_bssid" in data:
        location.wifi_bssid = (data["wifi_bssid"] or "").strip() or None

    db.session.commit()
    return jsonify({"success": True})


# --- Departments, classes, subjects ------------------------------------

@bp.get("/catalog")
@admin_required
def catalog():
    """Everything the session-creation form needs, in one call."""
    return jsonify(
        {
            "success": True,
            "departments": [
                {"id": d.id, "name": d.name}
                for d in Department.query.order_by(Department.name).all()
            ],
            "classes": [
                {"id": c.id, "name": c.name}
                for c in ClassGroup.query.order_by(ClassGroup.name).all()
            ],
            "subjects": [
                {
                    "id": s.id,
                    "name": s.name,
                    "code": s.code,
                    "department": s.department.name if s.department else None,
                }
                for s in Subject.query.order_by(Subject.name).all()
            ],
        }
    )


def _in_use(model_label, count, name):
    return jsonify(
        {"success": False, "error": "IN_USE",
         "message": f"{name} is still used by {count} {model_label}. "
                    "Reassign them first."}
    ), 409


@bp.post("/departments")
@admin_required
def create_department():
    name = (payload().get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400
    if Department.query.filter_by(name=name).first():
        return jsonify({"success": False, "error": "NAME_TAKEN",
                        "message": "That department already exists."}), 409

    dept = Department(name=name)
    db.session.add(dept)
    db.session.commit()
    return jsonify({"success": True, "id": dept.id}), 201


@bp.delete("/departments/<int:dept_id>")
@admin_required
def delete_department(dept_id):
    dept = db.session.get(Department, dept_id)
    if dept is None:
        abort(404)
    if dept.classes:
        return _in_use("class(es)", len(dept.classes), dept.name)
    if dept.subjects:
        return _in_use("subject(s)", len(dept.subjects), dept.name)

    db.session.delete(dept)
    db.session.commit()
    return jsonify({"success": True})


@bp.post("/classes")
@admin_required
def create_class():
    data = payload()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400

    group = ClassGroup(
        name=name,
        department_id=int(data["department_id"]) if data.get("department_id") else None,
        year=int(data["year"]) if data.get("year") else None,
        section=(data.get("section") or "").strip() or None,
    )
    db.session.add(group)
    db.session.commit()
    return jsonify({"success": True, "id": group.id}), 201


@bp.delete("/classes/<int:class_id>")
@admin_required
def delete_class(class_id):
    group = db.session.get(ClassGroup, class_id)
    if group is None:
        abort(404)
    if group.students:
        return _in_use("student(s)", len(group.students), group.name)

    db.session.delete(group)
    db.session.commit()
    return jsonify({"success": True})


@bp.post("/subjects")
@admin_required
def create_subject():
    data = payload()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400

    code = (data.get("code") or "").strip() or None
    if code and Subject.query.filter_by(code=code).first():
        return jsonify({"success": False, "error": "CODE_TAKEN",
                        "message": f"Subject code {code} is already in use."}), 409

    subject = Subject(
        name=name,
        code=code,
        department_id=int(data["department_id"]) if data.get("department_id") else None,
    )
    db.session.add(subject)
    db.session.commit()
    return jsonify({"success": True, "id": subject.id}), 201


@bp.delete("/subjects/<int:subject_id>")
@admin_required
def delete_subject(subject_id):
    subject = db.session.get(Subject, subject_id)
    if subject is None:
        abort(404)

    used = AttendanceSession.query.filter_by(subject_id=subject.id).count()
    if used:
        return _in_use("session(s)", used, subject.name)

    db.session.delete(subject)
    db.session.commit()
    return jsonify({"success": True})


@bp.get("/stats")
@admin_required
def stats():
    """Dashboard overview, including the things only an admin can fix."""
    from models.device import DeviceChangeRequest

    unconfigured = [
        loc.name for loc in Location.query.all() if not loc.network_list()
    ]

    return jsonify(
        {
            "success": True,
            "students": Student.query.count(),
            "teachers": Teacher.query.count(),
            "classes": ClassGroup.query.count(),
            "subjects": Subject.query.count(),
            "locations": Location.query.count(),
            "sessions": AttendanceSession.query.count(),
            "devices_bound": Device.query.filter_by(status="ACTIVE").count(),
            # Counted directly rather than by subtracting device count from
            # student count: a device belonging to a deactivated student
            # would make that arithmetic wrong, and can drive it negative.
            "students_without_device": Student.query.filter(
                Student.is_active.is_(True),
                ~Student.devices.any(Device.status == "ACTIVE"),
            ).count(),
            "pending_device_requests": DeviceChangeRequest.query.filter_by(
                status="PENDING"
            ).count(),
            "refused_attempts": AttendanceAttempt.query.filter(
                AttendanceAttempt.result != "ACCEPTED"
            ).count(),
            "flagged_records": Attendance.query.filter_by(status="FLAGGED").count(),
            # Locations with no network registered cannot pass the network
            # layer at all -- attendance there fails closed until an admin
            # fixes it. Surfacing it is the point of this panel.
            "locations_without_network": unconfigured,
        }
    )


# --- Devices -----------------------------------------------------------

@bp.get("/devices")
@admin_required
def list_devices():
    devices = Device.query.order_by(Device.registered_at.desc()).all()
    return jsonify(
        {
            "success": True,
            "devices": [
                {
                    "id": d.id,
                    "student": d.student.name,
                    "roll_no": d.student.roll_no,
                    "status": d.status,
                    "registered_at": d.registered_at.strftime("%d-%m-%Y %H:%M"),
                }
                for d in devices
            ],
        }
    )


@bp.post("/devices/<int:device_id>/revoke")
@admin_required
def revoke_device(device_id):
    """Unbind a device so the student can register a new one."""
    from util import utcnow

    device = db.session.get(Device, device_id)
    if device is None:
        abort(404)
    device.status = "REVOKED"
    device.revoked_at = utcnow()
    db.session.commit()
    return jsonify({"success": True, "message": "Device binding revoked."})


# --- Flagged attempts --------------------------------------------------

@bp.get("/attempts")
@admin_required
def list_attempts():
    """Recent failures. The trace a proxy attempt leaves behind."""
    attempts = (
        AttendanceAttempt.query.filter(AttendanceAttempt.result != "ACCEPTED")
        .order_by(AttendanceAttempt.attempted_at.desc())
        .limit(200)
        .all()
    )
    return jsonify(
        {
            "success": True,
            "attempts": [
                {
                    "id": a.id,
                    "student": a.student.name if a.student else None,
                    "roll_no": a.student.roll_no if a.student else None,
                    "session_id": a.session_id,
                    "at": a.attempted_at.strftime("%d-%m-%Y %H:%M:%S"),
                    "result": a.result,
                    "reason": a.failure_reason,
                    "distance_meters": (
                        round(a.distance_meters, 1) if a.distance_meters else None
                    ),
                    "source_ip": a.source_ip,
                }
                for a in attempts
            ],
        }
    )


# --- Reports -----------------------------------------------------------

@bp.get("/reports/daily")
@admin_required
def daily():
    records = report_service.daily_report()
    return jsonify(
        {
            "success": True,
            "count": len(records),
            "records": [
                {
                    "student": r.student.name,
                    "roll_no": r.student.roll_no,
                    "subject": r.session.subject.name,
                    "time": r.time.strftime("%H:%M") if r.time else "",
                    "status": r.status,
                }
                for r in records
            ],
        }
    )


@bp.get("/reports/student/<int:student_id>")
@admin_required
def student_report(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)

    rows, overall = report_service.monthly_report(student)
    return jsonify(
        {
            "success": True,
            "student": {"name": student.name, "roll_no": student.roll_no},
            "by_subject": rows,
            "overall_percentage": overall,
        }
    )


@bp.get("/reports/student/<int:student_id>/export.csv")
@admin_required
def student_csv(student_id):
    student = db.session.get(Student, student_id)
    if student is None:
        abort(404)

    return Response(
        report_service.student_csv(student),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=attendance-{student.roll_no}.csv"
            )
        },
    )

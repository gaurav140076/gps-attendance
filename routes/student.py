"""Student APIs: open sessions, device registration, history."""

from flask import Blueprint, jsonify, make_response

from routes.helpers import (
    attach_device_cookie,
    device_hash_from_cookie,
    payload,
)
from services import attendance_service, device_service, window_service
from services.auth_service import current_user, student_required
from models.attendance import Attendance

bp = Blueprint("student", __name__, url_prefix="/api/student")


@bp.get("/sessions")
@student_required
def open_sessions():
    """Only sessions a teacher currently has open.

    Returns an empty list when nothing is open, which is what leaves the
    student UI with nothing to press.
    """
    student = current_user()
    sessions = window_service.open_sessions_for_class(student.class_id)

    marked = {
        row.session_id
        for row in Attendance.query.filter_by(student_id=student.id).all()
    }

    return jsonify(
        {
            "success": True,
            "sessions": [
                {
                    "id": s.id,
                    "subject": s.subject.name,
                    "teacher": s.teacher.name,
                    "class": s.class_group.name,
                    "location": s.location.name,
                    "radius_meters": s.location.radius_meters,
                    "seconds_remaining": s.seconds_remaining(),
                    "already_marked": s.id in marked,
                }
                for s in sessions
            ],
        }
    )


@bp.get("/device")
@student_required
def device_status():
    student = current_user()
    device = student.active_device()
    presented = device_hash_from_cookie()

    return jsonify(
        {
            "success": True,
            "registered": device is not None,
            "is_this_device": bool(
                device and presented and device.device_hash == presented
            ),
            "registered_at": device.registered_at.isoformat() if device else None,
        }
    )


@bp.post("/device/register")
@student_required
def register_device():
    student = current_user()
    presented = device_hash_from_cookie()

    fresh = None
    if not presented:
        presented = device_service.new_device_hash()
        fresh = presented

    device, error = device_service.register(
        student, presented, payload().get("fingerprint")
    )

    if error == "DEVICE_OWNED_BY_ANOTHER_STUDENT":
        return jsonify(
            {"success": False, "error": error,
             "message": "This device is already registered to another student."}
        ), 409

    if error == "ALREADY_REGISTERED":
        return jsonify(
            {"success": False, "error": error,
             "message": "You already have a registered device. Request a "
                        "device change to move to a new phone."}
        ), 409

    response = make_response(
        jsonify({"success": True, "message": "This device is now registered."})
    )
    if fresh:
        attach_device_cookie(response, fresh)
    return response


@bp.post("/device/change-request")
@student_required
def request_device_change():
    student = current_user()
    presented = device_hash_from_cookie() or device_service.new_device_hash()

    req, error = device_service.request_change(
        student, presented, payload().get("fingerprint"), payload().get("reason")
    )

    if error == "ALREADY_PENDING":
        return jsonify(
            {"success": False, "error": error,
             "message": "You already have a device change waiting for approval."}
        ), 409

    return jsonify(
        {"success": True,
         "message": "Device change requested. Your teacher must approve it."}
    )


@bp.get("/attendance")
@student_required
def history():
    student = current_user()
    records = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.date.desc(), Attendance.time.desc())
        .all()
    )

    rows, overall = attendance_service.attendance_percentage(student)

    return jsonify(
        {
            "success": True,
            "overall_percentage": overall,
            "by_subject": rows,
            "records": [
                {
                    "date": r.date.strftime("%d-%m-%Y"),
                    "time": r.time.strftime("%H:%M") if r.time else "",
                    "subject": r.session.subject.name,
                    "status": r.status,
                    "distance_meters": (
                        round(r.distance_meters, 1) if r.distance_meters else None
                    ),
                    "override": r.is_override,
                }
                for r in records
            ],
        }
    )

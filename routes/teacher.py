"""Teacher APIs, including the switch the whole system hangs on."""

import io

from flask import Blueprint, Response, abort, current_app, jsonify

from extensions import db
from models.academic import ClassGroup, Subject
from models.attendance import Attendance
from models.device import DeviceChangeRequest
from models.location import Location
from models.people import Student
from models.session import AttendanceSession
from routes.helpers import payload
from services import (
    attendance_service,
    device_service,
    report_service,
    token_service,
    window_service,
)
from services.auth_service import current_user, teacher_required

bp = Blueprint("teacher", __name__, url_prefix="/api/teacher")


def _owned_session(session_id):
    """Fetch a session this teacher owns, or abort.

    Owning the session is what authorises opening it -- otherwise any
    teacher could open attendance for any class.
    """
    session = db.session.get(AttendanceSession, session_id)
    if session is None:
        abort(404)
    if session.teacher_id != current_user().id:
        abort(403)
    return session


@bp.post("/sessions")
@teacher_required
def create_session():
    """Create a session in SCHEDULED state. Nobody can mark yet."""
    data = payload()
    teacher = current_user()

    try:
        class_id = int(data["class_id"])
        subject_id = int(data["subject_id"])
        location_id = int(data["location_id"])
    except (KeyError, TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "MISSING_FIELDS",
             "message": "Class, subject and location are required."}
        ), 400

    for model, ident in (
        (ClassGroup, class_id),
        (Subject, subject_id),
        (Location, location_id),
    ):
        if db.session.get(model, ident) is None:
            return jsonify(
                {"success": False, "error": "NOT_FOUND",
                 "message": f"{model.__name__} {ident} does not exist."}
            ), 404

    # Copy the live config onto the row. Without this the model defaults
    # win and editing .env would have no effect on new sessions.
    session = AttendanceSession(
        teacher_id=teacher.id,
        class_id=class_id,
        subject_id=subject_id,
        location_id=location_id,
        window_seconds=current_app.config["DEFAULT_WINDOW_SECONDS"],
        token_rotation_seconds=current_app.config["TOKEN_ROTATION_SECONDS"],
        token_ttl_seconds=current_app.config["TOKEN_TTL_SECONDS"],
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(
        {"success": True, "session_id": session.id, "status": session.status}
    ), 201


ANCHOR_NOTES = {
    "NOT_REQUESTED": (
        "Using the classroom's saved coordinates."
    ),
    "NO_FIX": (
        "Could not read your position, so the classroom's saved coordinates "
        "are being used."
    ),
    "INVALID_FIX": (
        "Your device reported an impossible position, so the saved "
        "coordinates are being used."
    ),
    "NO_ACCURACY": (
        "Your device did not report an accuracy, so the saved coordinates "
        "are being used."
    ),
    "POOR_ACCURACY": (
        "Your location was too vague to centre the circle on, so the saved "
        "coordinates are being used. Move near a window and reopen if you "
        "want the circle centred on you."
    ),
}


def _anchor_note(code, reported_accuracy, limit):
    """Explain a refused anchor, with the numbers where we have them."""
    if code != "POOR_ACCURACY" or reported_accuracy is None:
        return ANCHOR_NOTES.get(code)
    try:
        reported = float(reported_accuracy)
    except (TypeError, ValueError):
        return ANCHOR_NOTES.get(code)

    return (
        f"Your device reported an accuracy of about {reported:,.0f} m, but "
        f"centring the circle needs {limit} m or better, so the classroom's "
        "saved coordinates are being used instead. A laptop positions itself "
        "by Wi-Fi and rarely does better than this; a phone with GPS will."
    )


@bp.post("/sessions/<int:session_id>/open")
@teacher_required
def open_window(session_id):
    """Turn attendance on, centring the geofence on the teacher."""
    session = _owned_session(session_id)
    data = payload()

    requested = data.get("window_seconds") or current_app.config[
        "DEFAULT_WINDOW_SECONDS"
    ]

    anchor = None
    if current_app.config["ANCHOR_ON_TEACHER_LOCATION"] and data.get("anchor") is not False:
        anchor = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "accuracy": data.get("accuracy"),
        }

    try:
        session, anchor_note = window_service.open_window(
            session,
            requested,
            current_app.config["MAX_WINDOW_SECONDS"],
            anchor=anchor,
            max_anchor_accuracy=current_app.config["MAX_ANCHOR_ACCURACY_METERS"],
        )
    except window_service.WindowError as exc:
        return jsonify(
            {"success": False, "error": exc.code, "message": exc.message}
        ), 409

    token = token_service.current_token(session)
    lat, lon, accuracy, source = session.anchor()

    return jsonify(
        {
            "success": True,
            "status": session.status,
            "opened_at": session.opened_at.isoformat(),
            "closes_at": session.closes_at.isoformat(),
            "window_seconds": session.window_seconds,
            "seconds_remaining": session.seconds_remaining(),
            "display_code": token.display_code if token else None,
            "anchor": {
                "source": source,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "accuracy": round(accuracy, 1) if accuracy else None,
                "radius_meters": session.location.radius_meters,
                "note": _anchor_note(
                    anchor_note,
                    (anchor or {}).get("accuracy"),
                    current_app.config["MAX_ANCHOR_ACCURACY_METERS"],
                ) if anchor_note else None,
            },
        }
    )


@bp.post("/sessions/<int:session_id>/close")
@teacher_required
def close_window(session_id):
    session = _owned_session(session_id)
    window_service.close_window(session)
    return jsonify({"success": True, "status": session.status})


@bp.get("/sessions/<int:session_id>/token")
@teacher_required
def current_token(session_id):
    """The token to display right now.

    Returns 403 when the window is not open, so the QR panel cannot show
    a live code for a closed session.
    """
    session = _owned_session(session_id)
    window_service.expire_if_due(session)

    if not session.is_window_open():
        return jsonify(
            {"success": False, "error": "WINDOW_NOT_OPEN",
             "status": session.status}
        ), 403

    token = token_service.current_token(session)
    return jsonify(
        {
            "success": True,
            "token": token.token,
            "display_code": token.display_code,
            "expires_at": token.expires_at.isoformat(),
            "rotation_seconds": session.token_rotation_seconds,
            "seconds_remaining": session.seconds_remaining(),
            "status": session.status,
        }
    )


@bp.get("/sessions/<int:session_id>/qr.png")
@teacher_required
def token_qr(session_id):
    """QR image for the current token.

    Degrades to 404 when the qrcode package is absent; the panel then
    shows the short code instead, and attendance still works.
    """
    session = _owned_session(session_id)
    window_service.expire_if_due(session)

    if not session.is_window_open():
        abort(403)

    try:
        import qrcode
    except ImportError:
        abort(404)

    token = token_service.current_token(session)
    image = qrcode.make(token.token)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)

    return Response(
        buf.read(),
        mimetype="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@bp.get("/sessions/<int:session_id>/attendance")
@teacher_required
def session_attendance(session_id):
    """Live roster: who is marked, who was refused, and why."""
    session = _owned_session(session_id)
    window_service.expire_if_due(session)

    roster = attendance_service.session_roster(session)
    enrolled = Student.query.filter_by(class_id=session.class_id).order_by(
        Student.roll_no.asc()
    ).all()

    return jsonify(
        {
            "success": True,
            "status": session.status,
            "seconds_remaining": session.seconds_remaining(),
            "total_enrolled": len(enrolled),
            "marked": [
                {
                    "student_id": r.student_id,
                    "roll_no": r.student.roll_no,
                    "name": r.student.name,
                    "time": r.time.strftime("%H:%M:%S") if r.time else "",
                    "status": r.status,
                    "distance_meters": (
                        round(r.distance_meters, 1) if r.distance_meters else None
                    ),
                    "override": r.is_override,
                    "flags": r.verification_flags,
                }
                for r in roster["marked"]
            ],
            "absent": [
                {"student_id": s.id, "roll_no": s.roll_no, "name": s.name}
                for s in enrolled
                if s.id not in roster["marked_ids"]
            ],
            "failures": [
                {
                    "student": f.student.name if f.student else "unknown",
                    "roll_no": f.student.roll_no if f.student else "",
                    "reason": f.failure_reason,
                    "at": f.attempted_at.strftime("%H:%M:%S"),
                    "distance_meters": (
                        round(f.distance_meters, 1) if f.distance_meters else None
                    ),
                }
                for f in roster["failures"]
            ],
        }
    )


@bp.post("/sessions/<int:session_id>/override")
@teacher_required
def override(session_id):
    """Mark a student by hand. Always audited."""
    session = _owned_session(session_id)
    data = payload()

    try:
        student_id = int(data["student_id"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"success": False, "error": "MISSING_FIELDS"}), 400

    student = db.session.get(Student, student_id)
    if student is None or student.class_id != session.class_id:
        return jsonify(
            {"success": False, "error": "NOT_ENROLLED",
             "message": "That student is not in this class."}
        ), 404

    present = str(data.get("present", "true")).lower() not in ("false", "0", "no")
    record = attendance_service.override(
        session, student, current_user().id, present=present,
        note=data.get("note"),
    )

    return jsonify(
        {"success": True, "status": record.status, "attendance_id": record.id}
    )


@bp.get("/sessions/<int:session_id>/export.csv")
@teacher_required
def export_session(session_id):
    session = _owned_session(session_id)
    csv_text = report_service.session_csv(session)
    filename = f"attendance-session-{session.id}.csv"
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.get("/device-requests")
@teacher_required
def device_requests():
    pending = DeviceChangeRequest.query.filter_by(status="PENDING").all()
    return jsonify(
        {
            "success": True,
            "requests": [
                {
                    "id": r.id,
                    "student": r.student.name,
                    "roll_no": r.student.roll_no,
                    "reason": r.reason,
                    "requested_at": r.requested_at.strftime("%d-%m-%Y %H:%M"),
                }
                for r in pending
            ],
        }
    )


@bp.post("/device-requests/<int:request_id>/approve")
@teacher_required
def approve_device_request(request_id):
    req = db.session.get(DeviceChangeRequest, request_id)
    if req is None:
        abort(404)

    _, error = device_service.approve_change(req, current_user().id)
    if error:
        return jsonify({"success": False, "error": error}), 409
    return jsonify({"success": True, "message": "Device change approved."})


@bp.post("/device-requests/<int:request_id>/reject")
@teacher_required
def reject_device_request(request_id):
    req = db.session.get(DeviceChangeRequest, request_id)
    if req is None:
        abort(404)

    error = device_service.reject_change(req, current_user().id)
    if error:
        return jsonify({"success": False, "error": error}), 409
    return jsonify({"success": True, "message": "Device change rejected."})

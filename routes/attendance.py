"""The attendance endpoint.

Thin by design: it collects the three things the client cannot be trusted
to assert (its own IP, its own device, the server's clock) and hands the
decision to the verification chain.
"""

from flask import Blueprint, jsonify

from routes.helpers import device_hash_from_cookie, payload, source_ip
from services import attendance_service
from services.auth_service import current_user, student_required

bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


@bp.post("/mark")
@student_required
def mark():
    data = payload()
    student = current_user()

    session_id = data.get("session_id")
    try:
        session_id = int(session_id)
    except (TypeError, ValueError):
        return jsonify(
            {"success": False, "error": "SESSION_NOT_FOUND",
             "message": "No attendance session was selected."}
        ), 400

    result = attendance_service.mark_attendance(
        student=student,
        session_id=session_id,
        payload=data,
        source_ip=source_ip(),
        device_hash=device_hash_from_cookie(),
    )

    return jsonify(result.to_dict()), result.status_code

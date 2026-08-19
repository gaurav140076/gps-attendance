"""Device binding: one account, one phone.

The device identity lives in a signed HttpOnly cookie, so the client can
present it but cannot choose it. Reading it from the request body would
make the whole layer decorative.
"""

import hashlib
import secrets

from itsdangerous import BadSignature, URLSafeSerializer

from extensions import db
from models.attendance import Attendance
from models.device import Device, DeviceChangeRequest
from util import utcnow

_SALT = "device-binding-v1"


def _serializer(secret_key):
    return URLSafeSerializer(secret_key, salt=_SALT)


def new_device_hash():
    """A fresh opaque device identifier."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def sign(secret_key, device_hash):
    return _serializer(secret_key).dumps(device_hash)


def unsign(secret_key, signed_value):
    """Recover a device hash from its cookie, or None if tampered with."""
    if not signed_value:
        return None
    try:
        return _serializer(secret_key).loads(signed_value)
    except BadSignature:
        return None


def read_cookie(request, secret_key, cookie_name):
    return unsign(secret_key, request.cookies.get(cookie_name))


def register(student, device_hash, fingerprint=None):
    """Bind a student to the device they are using.

    Fails if the device already belongs to somebody else -- that is the
    check that stops a phone being registered twice and passed along the
    row.
    """
    existing = Device.query.filter_by(device_hash=device_hash).first()
    if existing is not None:
        if existing.student_id == student.id:
            if existing.status != "ACTIVE":
                existing.status = "ACTIVE"
                existing.revoked_at = None
                db.session.commit()
            return existing, None
        return None, "DEVICE_OWNED_BY_ANOTHER_STUDENT"

    if student.active_device() is not None:
        return None, "ALREADY_REGISTERED"

    device = Device(
        student_id=student.id,
        device_hash=device_hash,
        fingerprint=(fingerprint or "")[:255],
        status="ACTIVE",
    )
    db.session.add(device)
    db.session.commit()
    return device, None


def check_binding(student, device_hash, enforce=True):
    """Verify the presented device belongs to this student.

    Returns ``(device, error_code)``.
    """
    if not enforce:
        return None, None

    if not device_hash:
        return None, "DEVICE_NOT_REGISTERED"

    device = Device.query.filter_by(device_hash=device_hash).first()
    if device is None or device.status != "ACTIVE":
        return None, "DEVICE_NOT_REGISTERED"

    if device.student_id != student.id:
        return None, "DEVICE_NOT_REGISTERED"

    return device, None


def check_unused_in_session(device, session_id, enforce=True):
    """One device cannot mark attendance for two students in a session.

    The database constraint is the real guarantee; this check exists to
    return a useful message instead of an integrity error.
    """
    if not enforce or device is None:
        return None

    clash = Attendance.query.filter_by(
        device_id=device.id, session_id=session_id
    ).first()
    if clash is not None and clash.student_id != device.student_id:
        return "DEVICE_ALREADY_USED"
    return None


def request_change(student, new_device_hash, fingerprint=None, reason=None):
    """Raise a rebinding request for a teacher or admin to approve."""
    pending = DeviceChangeRequest.query.filter_by(
        student_id=student.id, status="PENDING"
    ).first()
    if pending is not None:
        return pending, "ALREADY_PENDING"

    req = DeviceChangeRequest(
        student_id=student.id,
        new_device_hash=new_device_hash,
        fingerprint=(fingerprint or "")[:255],
        reason=(reason or "")[:255],
        status="PENDING",
    )
    db.session.add(req)
    db.session.commit()
    return req, None


def approve_change(req, approver_id):
    """Revoke the old binding and install the new one."""
    if req.status != "PENDING":
        return None, "NOT_PENDING"

    clash = Device.query.filter_by(device_hash=req.new_device_hash).first()
    if clash is not None and clash.student_id != req.student_id:
        req.status = "REJECTED"
        db.session.commit()
        return None, "DEVICE_OWNED_BY_ANOTHER_STUDENT"

    now = utcnow()
    for device in Device.query.filter_by(student_id=req.student_id, status="ACTIVE"):
        device.status = "REVOKED"
        device.revoked_at = now

    if clash is not None:
        clash.status = "ACTIVE"
        clash.revoked_at = None
        device = clash
    else:
        device = Device(
            student_id=req.student_id,
            device_hash=req.new_device_hash,
            fingerprint=req.fingerprint,
            status="ACTIVE",
            approved_by=approver_id,
        )
        db.session.add(device)

    req.status = "APPROVED"
    req.decided_at = now
    req.decided_by = approver_id
    db.session.commit()
    return device, None


def reject_change(req, approver_id):
    if req.status != "PENDING":
        return "NOT_PENDING"
    req.status = "REJECTED"
    req.decided_at = utcnow()
    req.decided_by = approver_id
    db.session.commit()
    return None

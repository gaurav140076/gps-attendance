"""Device binding: one account, one phone."""

from extensions import db
from util import utcnow


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    # Unique across the whole table, which is what stops one phone being
    # registered to two accounts and passed around the room.
    device_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)

    fingerprint = db.Column(db.String(255))
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    registered_at = db.Column(db.DateTime, default=utcnow)
    approved_by = db.Column(db.Integer)
    revoked_at = db.Column(db.DateTime)

    student = db.relationship("Student", back_populates="devices")

    def __repr__(self):
        return f"<Device {self.id} student={self.student_id} {self.status}>"


class DeviceChangeRequest(db.Model):
    """A student asking to move their binding to a new phone.

    Deliberately not self-service: if a student could rebind at will,
    device binding would stop preventing anything.
    """

    __tablename__ = "device_change_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    new_device_hash = db.Column(db.String(128), nullable=False)
    fingerprint = db.Column(db.String(255))
    reason = db.Column(db.String(255))
    status = db.Column(db.String(30), nullable=False, default="PENDING")
    requested_at = db.Column(db.DateTime, default=utcnow)
    decided_at = db.Column(db.DateTime)
    decided_by = db.Column(db.Integer)

    student = db.relationship("Student")

    def __repr__(self):
        return f"<DeviceChangeRequest {self.id} {self.status}>"

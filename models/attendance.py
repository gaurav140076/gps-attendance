"""Attendance records and the log of every attempt to create one."""

from extensions import db
from util import utcnow

PRESENT = "PRESENT"
FLAGGED = "FLAGGED"
REJECTED = "REJECTED"


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False
    )

    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    distance_meters = db.Column(db.Float)
    effective_meters = db.Column(db.Float)

    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"))
    token_id = db.Column(db.Integer, db.ForeignKey("session_tokens.id"))
    source_ip = db.Column(db.String(64))

    verification_flags = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default=PRESENT)

    # Set when a teacher marks somebody present by hand.
    is_override = db.Column(db.Boolean, default=False, nullable=False)
    override_by = db.Column(db.Integer)
    override_note = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=utcnow)

    student = db.relationship("Student", back_populates="attendance")
    session = db.relationship("AttendanceSession", back_populates="attendance")
    device = db.relationship("Device")

    __table_args__ = (
        # One record per student per session.
        db.UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),
        # One device cannot mark two students in the same session. This
        # lives in the database rather than only in application code
        # because two concurrent requests can both pass an in-process
        # check and then both insert.
        db.UniqueConstraint("device_id", "session_id", name="uq_attendance_device_session"),
    )

    def __repr__(self):
        return f"<Attendance s={self.student_id} sess={self.session_id} {self.status}>"


class AttendanceAttempt(db.Model):
    """Every attempt, successful or not.

    This is what turns proxy from an invisible act into a visible one:
    a run of WRONG_NETWORK or DEVICE_ALREADY_USED failures is exactly the
    trace an attempt leaves behind.

    It is also the most privacy-sensitive table here -- it records where
    students were when they *failed*, including the ones who simply had
    bad Wi-Fi. Give it the shortest retention of anything in the schema.
    """

    __tablename__ = "attendance_attempts"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    session_id = db.Column(db.Integer, db.ForeignKey("attendance_sessions.id"))

    attempted_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    result = db.Column(db.String(20), nullable=False)
    failure_reason = db.Column(db.String(60))

    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    distance_meters = db.Column(db.Float)

    device_hash = db.Column(db.String(128))
    source_ip = db.Column(db.String(64))
    note = db.Column(db.String(255))

    student = db.relationship("Student")
    session = db.relationship("AttendanceSession")

    def __repr__(self):
        return f"<Attempt {self.result} {self.failure_reason}>"

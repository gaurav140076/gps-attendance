"""Attendance sessions and their rotating tokens.

The session row carries the state machine that answers the only question
that matters before anything else: has the teacher turned attendance on?
"""

from extensions import db
from util import utcnow

SCHEDULED = "SCHEDULED"
ACTIVE = "ACTIVE"
CLOSED = "CLOSED"


class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)

    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # SCHEDULED -> ACTIVE -> CLOSED. CLOSED is terminal.
    status = db.Column(db.String(20), nullable=False, default=SCHEDULED)

    # NULL until the teacher presses Open Attendance.
    opened_at = db.Column(db.DateTime)
    closes_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    # Fallbacks only. create_session copies the live config onto the row
    # so a change in .env reaches new sessions; existing rows keep the
    # timing they were created with.
    window_seconds = db.Column(db.Integer, nullable=False, default=120)
    token_rotation_seconds = db.Column(db.Integer, nullable=False, default=30)
    token_ttl_seconds = db.Column(db.Integer, nullable=False, default=35)

    # Where the circle is actually centred. Captured from the teacher's
    # device when they open the window; NULL means fall back to the
    # classroom's saved coordinates.
    anchor_latitude = db.Column(db.Float)
    anchor_longitude = db.Column(db.Float)
    anchor_accuracy = db.Column(db.Float)
    anchor_source = db.Column(db.String(20), nullable=False, default="LOCATION")

    created_at = db.Column(db.DateTime, default=utcnow)

    teacher = db.relationship("Teacher", back_populates="sessions")
    location = db.relationship("Location", back_populates="sessions")
    class_group = db.relationship("ClassGroup")
    subject = db.relationship("Subject")
    tokens = db.relationship(
        "SessionToken", back_populates="session", cascade="all, delete-orphan"
    )
    attendance = db.relationship(
        "Attendance", back_populates="session", cascade="all, delete-orphan"
    )

    def anchor(self):
        """The centre of the geofence for this session.

        Returns ``(latitude, longitude, accuracy, source)``. ``accuracy``
        is None for a surveyed classroom point, which is treated as
        exact; a teacher-captured anchor carries its own error and the
        geofence has to forgive it.
        """
        if self.anchor_source == "TEACHER" and self.anchor_latitude is not None:
            return (
                self.anchor_latitude,
                self.anchor_longitude,
                self.anchor_accuracy,
                "TEACHER",
            )
        return (
            self.location.latitude,
            self.location.longitude,
            None,
            "LOCATION",
        )

    def is_window_open(self, now=None):
        """Whether attendance can be marked *right now*.

        Both halves are required. Checking ``status`` alone would leave a
        session open forever if the process that should have closed it
        died.
        """
        if self.status != ACTIVE:
            return False
        if self.opened_at is None or self.closes_at is None:
            return False
        now = now or utcnow()
        return self.opened_at <= now <= self.closes_at

    def seconds_remaining(self, now=None):
        if self.status != ACTIVE or self.closes_at is None:
            return 0
        now = now or utcnow()
        return max(0, int((self.closes_at - now).total_seconds()))

    def __repr__(self):
        return f"<AttendanceSession {self.id} {self.status}>"


class SessionToken(db.Model):
    """One rotation of the teacher's QR code.

    ``token`` is what the QR encodes; ``display_code`` is the short form
    shown underneath it so a student whose camera will not cooperate can
    type it instead. Both expire together.
    """

    __tablename__ = "session_tokens"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False
    )
    token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    display_code = db.Column(db.String(12), nullable=False, index=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    session = db.relationship("AttendanceSession", back_populates="tokens")

    def is_valid(self, now=None):
        now = now or utcnow()
        return self.issued_at <= now <= self.expires_at

    def __repr__(self):
        return f"<SessionToken {self.display_code} session={self.session_id}>"

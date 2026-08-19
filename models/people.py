"""Students, teachers and admins."""

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from util import utcnow


class PasswordMixin:
    """Password hashing shared by every account type.

    Passwords are never stored; only the hash is.
    """

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw)


class Student(PasswordMixin, db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(40), nullable=False, unique=True)
    email = db.Column(db.String(160), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    class_group = db.relationship("ClassGroup", back_populates="students")
    devices = db.relationship("Device", back_populates="student")
    attendance = db.relationship("Attendance", back_populates="student")

    role = "STUDENT"

    def active_device(self):
        """The one device this account may mark attendance from."""
        return next((d for d in self.devices if d.status == "ACTIVE"), None)

    def __repr__(self):
        return f"<Student {self.roll_no} {self.name}>"


class Teacher(PasswordMixin, db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)

    # The institution's own staff code, typed in by an admin -- the
    # teacher equivalent of a student's roll number. Unique but optional,
    # so an existing teacher without one is still valid; SQLite permits
    # many NULLs in a unique column.
    teacher_id = db.Column(db.String(40), unique=True)

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    sessions = db.relationship("AttendanceSession", back_populates="teacher")

    role = "TEACHER"

    def __repr__(self):
        return f"<Teacher {self.name}>"


class Admin(PasswordMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    role = "ADMIN"

    def __repr__(self):
        return f"<Admin {self.name}>"

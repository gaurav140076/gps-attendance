"""Model package.

Importing every model here means ``db.create_all()`` sees the whole
schema regardless of which module the caller imported first.
"""

from models.academic import ClassGroup, Department, Subject
from models.attendance import (
    FLAGGED,
    PRESENT,
    REJECTED,
    Attendance,
    AttendanceAttempt,
)
from models.device import Device, DeviceChangeRequest
from models.location import Location
from models.people import Admin, Student, Teacher
from models.session import (
    ACTIVE,
    CLOSED,
    SCHEDULED,
    AttendanceSession,
    SessionToken,
)

__all__ = [
    "ACTIVE",
    "CLOSED",
    "FLAGGED",
    "PRESENT",
    "REJECTED",
    "SCHEDULED",
    "Admin",
    "Attendance",
    "AttendanceAttempt",
    "AttendanceSession",
    "ClassGroup",
    "Department",
    "Device",
    "DeviceChangeRequest",
    "Location",
    "SessionToken",
    "Student",
    "Subject",
    "Teacher",
]

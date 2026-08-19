"""Report generation and CSV export.

CSV is produced with the standard library so exports always work. Excel
and PDF are left to the optional dependencies in requirements.txt rather
than being claimed here and failing at the moment somebody needs them.
"""

import csv
import io
from datetime import timedelta

from models.attendance import REJECTED, Attendance
from models.people import Student
from models.session import AttendanceSession
from util import utcnow


def daily_report(day=None):
    day = day or utcnow().date()
    start = day
    end = day + timedelta(days=1)

    records = (
        Attendance.query.filter(Attendance.date >= start, Attendance.date < end)
        .order_by(Attendance.time.asc())
        .all()
    )
    return [r for r in records if r.status != REJECTED]


def monthly_report(student, year=None, month=None):
    """Per-subject totals for one student."""
    now = utcnow()
    year = year or now.year
    month = month or now.month

    sessions = AttendanceSession.query.filter_by(class_id=student.class_id).all()
    held = {}
    for session in sessions:
        if session.opened_at is None:
            continue
        if session.opened_at.year != year or session.opened_at.month != month:
            continue
        held.setdefault(session.subject.name, 0)
        held[session.subject.name] += 1

    present = {}
    for record in Attendance.query.filter_by(student_id=student.id).all():
        if record.status == REJECTED:
            continue
        opened = record.session.opened_at
        if opened is None or opened.year != year or opened.month != month:
            continue
        name = record.session.subject.name
        present[name] = present.get(name, 0) + 1

    rows = []
    total_present = 0
    total_held = 0
    for subject, total in sorted(held.items()):
        got = present.get(subject, 0)
        total_present += got
        total_held += total
        rows.append(
            {
                "subject": subject,
                "present": got,
                "total": total,
                "percentage": round(100.0 * got / total, 2) if total else 0.0,
            }
        )

    overall = round(100.0 * total_present / total_held, 2) if total_held else 0.0
    return rows, overall


def session_csv(session):
    """Attendance for one session.

    Coordinates are deliberately excluded. A class list does not need a
    location history attached to it; the audit view is where that lives.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["Roll No", "Name", "Status", "Time", "Distance (m)", "Override", "Flags"]
    )

    records = (
        Attendance.query.filter_by(session_id=session.id)
        .join(Student, Attendance.student_id == Student.id)
        .order_by(Student.roll_no.asc())
        .all()
    )

    for record in records:
        writer.writerow(
            [
                record.student.roll_no,
                record.student.name,
                record.status,
                record.time.strftime("%H:%M:%S") if record.time else "",
                round(record.distance_meters, 1) if record.distance_meters else "",
                "YES" if record.is_override else "",
                record.verification_flags or "",
            ]
        )

    return buf.getvalue()


def student_csv(student):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Subject", "Status", "Time", "Distance (m)"])

    records = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.date.asc(), Attendance.time.asc())
        .all()
    )
    for record in records:
        writer.writerow(
            [
                record.date.strftime("%d-%m-%Y"),
                record.session.subject.name,
                record.status,
                record.time.strftime("%H:%M:%S") if record.time else "",
                round(record.distance_meters, 1) if record.distance_meters else "",
            ]
        )

    return buf.getvalue()

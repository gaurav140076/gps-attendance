"""Departments, classes and subjects."""

from extensions import db
from util import utcnow


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)

    classes = db.relationship("ClassGroup", back_populates="department")
    subjects = db.relationship("Subject", back_populates="department")

    def __repr__(self):
        return f"<Department {self.name}>"


class ClassGroup(db.Model):
    """A class/section, e.g. "CSE 3A".

    Named ClassGroup because `class` is a Python keyword.
    """

    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    year = db.Column(db.Integer)
    section = db.Column(db.String(10))

    department = db.relationship("Department", back_populates="classes")
    students = db.relationship("Student", back_populates="class_group")

    def __repr__(self):
        return f"<ClassGroup {self.name}>"


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(30), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    created_at = db.Column(db.DateTime, default=utcnow)

    department = db.relationship("Department", back_populates="subjects")

    def __repr__(self):
        return f"<Subject {self.code} {self.name}>"

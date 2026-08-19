"""Demo data for local development and demonstrations.

The seeded classroom allows loopback and private-LAN addresses so the
network layer passes when you test from your own machine or a phone on
the same Wi-Fi. A real classroom would list only its own egress address.
"""

from extensions import db
from models.academic import ClassGroup, Department, Subject
from models.location import Location
from models.people import Admin, Student, Teacher

DEMO_PASSWORD = "password123"
TEACHER_PASSWORD = "Teacher@123"

# Loopback plus the RFC1918 ranges, so a phone on the same Wi-Fi as the
# laptop running this can mark attendance during a demo.
DEV_NETWORKS = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


def seed():
    db.create_all()

    if Department.query.first() is not None:
        print("Data already present; skipping seed.")
        return

    cse = Department(name="Computer Science")
    it = Department(name="Information Technology")
    db.session.add_all([cse, it])
    db.session.flush()

    class_3a = ClassGroup(name="CSE 3A", department_id=cse.id, year=3, section="A")
    class_3b = ClassGroup(name="CSE 3B", department_id=cse.id, year=3, section="B")
    db.session.add_all([class_3a, class_3b])
    db.session.flush()

    subjects = [
        Subject(name="Data Structures", code="CS301", department_id=cse.id),
        Subject(name="Database Management", code="CS302", department_id=cse.id),
        Subject(name="Operating Systems", code="CS303", department_id=cse.id),
    ]
    db.session.add_all(subjects)

    room = Location(
        name="CS Block - Room 204",
        latitude=28.613900,
        longitude=77.209000,
        radius_meters=10,
        allowed_networks=DEV_NETWORKS,
    )
    hall = Location(
        name="Main Lecture Hall",
        latitude=28.614500,
        longitude=77.209800,
        # A 30 m hall needs a radius that covers the back row. The 10 m
        # default is a classroom number, not a universal one.
        radius_meters=25,
        allowed_networks=DEV_NETWORKS,
    )
    db.session.add_all([room, hall])

    admin = Admin(name="System Admin", email="admin@college.edu")
    admin.set_password(DEMO_PASSWORD)
    db.session.add(admin)

    teacher = Teacher(
        teacher_id="TCH000",
        name="Mr. Sharma",
        email="sharma@college.edu",
        department_id=cse.id,
    )
    teacher.set_password(DEMO_PASSWORD)
    db.session.add(teacher)

    # Three plain accounts for demos and screenshots. An admin can create
    # more, with their own staff codes, from the Teachers page.
    for n in (1, 2, 3):
        extra = Teacher(
            teacher_id=f"TCH00{n}",
            name=f"Teacher {n}",
            email=f"teacher{n}@gmail.com",
            department_id=cse.id,
        )
        extra.set_password(TEACHER_PASSWORD)
        db.session.add(extra)

    db.session.flush()

    roster = [
        ("Gaurav Roy", "101"),
        ("Priya Nair", "102"),
        ("Anjali Menon", "103"),
        ("Rohit Verma", "104"),
        ("Sneha Iyer", "105"),
    ]
    for name, roll in roster:
        student = Student(
            name=name,
            roll_no=roll,
            email=f"{roll}@college.edu",
            department_id=cse.id,
            class_id=class_3a.id,
        )
        student.set_password(DEMO_PASSWORD)
        db.session.add(student)

    db.session.commit()

    print("Seeded demo data.\n")
    print("  ROLE      TEACHER ID  EMAIL                  PASSWORD")
    print("  " + "-" * 62)
    print(f"  Admin     -           admin@college.edu      {DEMO_PASSWORD}")
    print(f"  Teacher   TCH000      sharma@college.edu     {DEMO_PASSWORD}")
    for n in (1, 2, 3):
        print(f"  Teacher   TCH00{n}      teacher{n}@gmail.com     "
              f"{TEACHER_PASSWORD}")
    print(f"  Students  101-105     101@college.edu ...    {DEMO_PASSWORD}")
    print()
    print(f"  Classroom '{room.name}' at {room.latitude}, {room.longitude} "
          f"({room.radius_meters} m)")


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        seed()

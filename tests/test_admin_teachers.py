"""Admin-created teachers and their manually assigned staff codes."""

from conftest import PASSWORD, login, student_client, teacher_client
from extensions import db
from models.people import Admin, Teacher


def admin_client(app):
    admin = Admin(name="System Admin", email="admin@college.edu")
    admin.set_password(PASSWORD)
    db.session.add(admin)
    db.session.commit()

    c = app.test_client()
    login(c, "admin@college.edu", role="ADMIN")
    return c


def create(client, **kwargs):
    body = {
        "name": "Ms. Das",
        "email": "das@college.edu",
        "password": PASSWORD,
    }
    body.update(kwargs)
    return client.post("/api/admin/teachers", json=body)


def test_admin_creates_a_teacher_with_a_manual_id(app, data):
    client = admin_client(app)
    response = create(client, teacher_id="TCH042")

    assert response.status_code == 201
    assert response.get_json()["teacher_id"] == "TCH042"

    saved = Teacher.query.filter_by(email="das@college.edu").first()
    assert saved is not None
    assert saved.teacher_id == "TCH042"


def test_the_created_teacher_can_log_in(app, data):
    """An account that cannot log in has not really been created."""
    client = admin_client(app)
    create(client, teacher_id="TCH042")

    fresh = app.test_client()
    response = login(fresh, "das@college.edu", role="TEACHER")

    assert response.status_code == 200
    assert response.get_json()["role"] == "TEACHER"


def test_teacher_id_is_optional(app, data):
    client = admin_client(app)
    response = create(client, email="notid@college.edu")

    assert response.status_code == 201
    assert Teacher.query.filter_by(email="notid@college.edu").first().teacher_id is None


def test_duplicate_teacher_id_is_refused(app, data):
    """Two teachers sharing a code would make every report grouped by it
    wrong, so the collision is caught rather than stored."""
    client = admin_client(app)
    create(client, teacher_id="TCH042")

    response = create(client, email="other@college.edu", teacher_id="TCH042")

    assert response.status_code == 409
    assert response.get_json()["error"] == "TEACHER_ID_TAKEN"


def test_duplicate_email_is_refused(app, data):
    client = admin_client(app)
    create(client, teacher_id="TCH042")

    response = create(client, teacher_id="TCH043")

    assert response.status_code == 409
    assert response.get_json()["error"] == "EMAIL_TAKEN"


def test_teacher_id_can_be_set_later(app, data):
    client = admin_client(app)
    teacher = data["teacher"]

    response = client.put(
        f"/api/admin/teachers/{teacher.id}", json={"teacher_id": "TCH999"}
    )

    assert response.status_code == 200
    assert db.session.get(Teacher, teacher.id).teacher_id == "TCH999"


def test_updating_to_a_taken_id_is_refused(app, data):
    client = admin_client(app)
    create(client, teacher_id="TCH042")

    response = client.put(
        f"/api/admin/teachers/{data['teacher'].id}", json={"teacher_id": "TCH042"}
    )

    assert response.status_code == 409
    assert "already assigned" in response.get_json()["message"]


def test_teacher_id_can_be_cleared(app, data):
    client = admin_client(app)
    client.put(f"/api/admin/teachers/{data['teacher'].id}",
               json={"teacher_id": "TCH999"})

    client.put(f"/api/admin/teachers/{data['teacher'].id}",
               json={"teacher_id": ""})

    assert db.session.get(Teacher, data["teacher"].id).teacher_id is None


def test_listing_includes_the_teacher_id(app, data):
    client = admin_client(app)
    create(client, teacher_id="TCH042")

    rows = client.get("/api/admin/teachers").get_json()["teachers"]
    codes = {r["teacher_id"] for r in rows}

    assert "TCH042" in codes


def test_a_teacher_cannot_create_teachers(app, data):
    """Only admins hold the account register."""
    client = teacher_client(app, "sharma@college.edu")
    assert create(client).status_code == 403


def test_a_student_cannot_create_teachers(app, data):
    client = student_client(app, "101@college.edu")
    assert create(client).status_code == 403

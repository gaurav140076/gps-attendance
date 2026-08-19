"""Teacher-anchored geofence.

The circle is centred on wherever the teacher was standing when they
opened the window. That removes the surveying step, but it also means the
centre now carries its own error -- so the geofence has to forgive the
teacher's uncertainty as well as the student's.
"""

import pytest

from conftest import mark, student_client, teacher_client
from extensions import db
from services import token_service, window_service
from services.geolocation import INSIDE, OUTSIDE, check_geofence, haversine_meters

# The seeded classroom, and a point ~55 m north of it.
ROOM_LAT, ROOM_LON = 28.613900, 77.209000
FAR_LAT = 28.614395


def open_with_anchor(data, lat=None, lon=None, accuracy=None, window=120):
    anchor = None
    if lat is not None:
        anchor = {"latitude": lat, "longitude": lon, "accuracy": accuracy}
    session, note = window_service.open_window(
        data["session"], window, 300, anchor=anchor, max_anchor_accuracy=30
    )
    return token_service.current_token(session).token, note


# --- The maths: two errors compound -------------------------------------

def test_anchor_error_is_forgiven_on_top_of_the_student_error():
    """Two phones side by side can differ by the sum of their errors.

    Without anchor credit, a student standing next to the teacher is
    rejected for the teacher's GPS noise.
    """
    # 28 m apart, student ±12 m, teacher's anchor ±20 m.
    without = check_geofence(28.0, 12.0, 10, 35, 50)
    with_anchor = check_geofence(28.0, 12.0, 10, 35, 50,
                                 anchor_accuracy=20.0, anchor_credit=25)

    assert without[0] == OUTSIDE      # 28 - 12 = 16 > 10
    assert with_anchor[0] == INSIDE   # 28 - 12 - 20 = -4 <= 10


def test_anchor_credit_is_capped():
    """A vague anchor cannot buy unlimited forgiveness."""
    verdict, effective = check_geofence(
        120.0, 10.0, 10, 35, 50, anchor_accuracy=999.0, anchor_credit=25
    )
    assert verdict == OUTSIDE
    assert effective == pytest.approx(85.0)  # 120 - 10 - 25


def test_surveyed_point_gets_no_anchor_credit():
    """A surveyed coordinate is treated as exact, as before."""
    verdict, effective = check_geofence(28.0, 12.0, 10, 35, 50,
                                        anchor_accuracy=None, anchor_credit=25)
    assert verdict == OUTSIDE
    assert effective == pytest.approx(16.0)


def test_far_student_still_refused_with_a_generous_anchor():
    """The whole point: the circle moved, it did not disappear."""
    verdict, _ = check_geofence(200.0, 10.0, 10, 35, 50,
                                anchor_accuracy=25.0, anchor_credit=25)
    assert verdict == OUTSIDE


# --- Setting the anchor ---------------------------------------------------

def test_anchor_defaults_to_the_saved_classroom(app, data):
    open_with_anchor(data)
    lat, lon, accuracy, source = data["session"].anchor()

    assert source == "LOCATION"
    assert lat == pytest.approx(ROOM_LAT)
    assert accuracy is None


def test_teacher_position_becomes_the_anchor(app, data):
    """Open from 200 m away and the classroom moves there."""
    open_with_anchor(data, lat=28.615700, lon=77.210500, accuracy=9.0)
    lat, lon, accuracy, source = data["session"].anchor()

    assert source == "TEACHER"
    assert lat == pytest.approx(28.615700)
    assert lon == pytest.approx(77.210500)
    assert accuracy == pytest.approx(9.0)


def test_vague_anchor_is_refused_and_falls_back(app, data):
    """A circle centred on a bad fix silently moves the classroom."""
    _, note = open_with_anchor(data, lat=28.6157, lon=77.2105, accuracy=120.0)

    assert note == "POOR_ACCURACY"
    assert data["session"].anchor()[3] == "LOCATION"


def test_anchor_without_accuracy_is_refused(app, data):
    _, note = open_with_anchor(data, lat=28.6157, lon=77.2105, accuracy=None)
    assert note == "NO_ACCURACY"
    assert data["session"].anchor()[3] == "LOCATION"


def test_impossible_anchor_coordinates_are_refused(app, data):
    _, note = open_with_anchor(data, lat=999.0, lon=999.0, accuracy=5.0)
    assert note == "INVALID_FIX"
    assert data["session"].anchor()[3] == "LOCATION"


# --- End to end through the chain -----------------------------------------

def test_student_at_the_teacher_position_is_inside(app, data):
    """Teacher opens from the far end of the building; a student there
    is admitted even though the saved classroom is 55 m away."""
    token, note = open_with_anchor(data, lat=FAR_LAT, lon=ROOM_LON, accuracy=8.0)
    assert note is None

    client = student_client(app, "101@college.edu")
    response = mark(client, data["session"].id, token,
                    lat=FAR_LAT + 0.00002, lon=ROOM_LON, accuracy=8.0)

    assert response.get_json()["success"] is True


def test_student_at_the_old_classroom_is_now_outside(app, data):
    """The circle moved with the teacher, so the old spot is out."""
    token, _ = open_with_anchor(data, lat=FAR_LAT, lon=ROOM_LON, accuracy=6.0)

    # Confirm the two points really are far apart.
    assert haversine_meters(FAR_LAT, ROOM_LON, ROOM_LAT, ROOM_LON) > 45

    client = student_client(app, "101@college.edu")
    body = mark(client, data["session"].id, token,
                lat=ROOM_LAT, lon=ROOM_LON, accuracy=5.0).get_json()

    assert body["success"] is False
    assert body["error"] == "OUTSIDE_RADIUS"


def test_open_endpoint_reports_the_anchor(app, data):
    client = teacher_client(app, "sharma@college.edu")
    response = client.post(
        f"/api/teacher/sessions/{data['session'].id}/open",
        json={"window_seconds": 120, "latitude": 28.6157,
              "longitude": 77.2105, "accuracy": 7.5},
    )
    anchor = response.get_json()["anchor"]

    assert anchor["source"] == "TEACHER"
    assert anchor["accuracy"] == 7.5
    assert anchor["radius_meters"] == 10
    assert anchor["note"] is None


def test_open_endpoint_explains_a_refused_anchor(app, data):
    client = teacher_client(app, "sharma@college.edu")
    response = client.post(
        f"/api/teacher/sessions/{data['session'].id}/open",
        json={"window_seconds": 120, "latitude": 28.6157,
              "longitude": 77.2105, "accuracy": 200},
    )
    anchor = response.get_json()["anchor"]

    assert anchor["source"] == "LOCATION"
    # The note must carry the actual figures: "too vague" with no numbers
    # is undiagnosable for whoever has to fix it.
    assert "200 m" in anchor["note"]
    assert "30 m" in anchor["note"]


def test_teacher_can_opt_out_of_anchoring(app, data):
    client = teacher_client(app, "sharma@college.edu")
    response = client.post(
        f"/api/teacher/sessions/{data['session'].id}/open",
        json={"window_seconds": 120, "anchor": False,
              "latitude": 28.6157, "longitude": 77.2105, "accuracy": 5},
    )

    assert response.get_json()["anchor"]["source"] == "LOCATION"


def test_anchor_is_fixed_once_the_window_is_open(app, data):
    """Re-opening is refused, so the circle cannot move under students
    who have already marked."""
    open_with_anchor(data, lat=FAR_LAT, lon=ROOM_LON, accuracy=8.0)
    before = data["session"].anchor()

    with pytest.raises(window_service.WindowError):
        open_with_anchor(data, lat=ROOM_LAT, lon=ROOM_LON, accuracy=8.0)

    assert data["session"].anchor() == before


def test_exact_anchor_match_raises_the_signal(app, data):
    """The mock-location heuristic follows the anchor, not the classroom.

    The record still counts as present; only the signal is recorded.
    """
    token, _ = open_with_anchor(data, lat=FAR_LAT, lon=ROOM_LON, accuracy=6.0)

    client = student_client(app, "101@college.edu")
    body = mark(client, data["session"].id, token,
                lat=FAR_LAT, lon=ROOM_LON, accuracy=5.0).get_json()

    assert body["success"] is True
    assert body["status"] == "PRESENT"
    assert "EXACT_CLASSROOM_MATCH" in body["flags"]

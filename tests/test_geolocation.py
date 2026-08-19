"""Geofence maths.

TC04-TC06 and TC11 from the README. These are the cases worth re-running
at the real classroom before rollout: they decide whether a 10 m radius
admits the people in the room and refuses the people outside it.
"""

import pytest

from services.geolocation import (
    INSIDE,
    OUTSIDE,
    RETRY_POOR_ACCURACY,
    check_geofence,
    haversine_meters,
    valid_coordinates,
)

RADIUS = 10
CREDIT = 35
MAX_ACC = 50


def geofence(distance, accuracy):
    return check_geofence(distance, accuracy, RADIUS, CREDIT, MAX_ACC)


# --- Haversine ---------------------------------------------------------

def test_zero_distance():
    assert haversine_meters(28.6139, 77.2090, 28.6139, 77.2090) == pytest.approx(0)


def test_known_short_distance():
    """~4 m apart: the front-row case."""
    d = haversine_meters(28.613900, 77.209000, 28.613935, 77.209021)
    assert 3.0 < d < 6.0


def test_one_degree_latitude_is_about_111km():
    d = haversine_meters(0.0, 0.0, 1.0, 0.0)
    assert d == pytest.approx(111_195, rel=0.001)


def test_distance_is_symmetric():
    a = haversine_meters(28.6139, 77.2090, 28.6200, 77.2150)
    b = haversine_meters(28.6200, 77.2150, 28.6139, 77.2090)
    assert a == pytest.approx(b)


# --- The documented worked examples ------------------------------------

def test_tc04_front_row_good_fix_is_inside():
    verdict, effective = geofence(4.2, 8.4)
    assert verdict == INSIDE
    assert effective == pytest.approx(-4.2)


def test_tc05_in_room_noisy_indoor_fix_is_inside():
    """The case a naive `distance <= 10` test would falsely reject."""
    verdict, effective = geofence(28.0, 24.0)
    assert verdict == INSIDE
    assert effective == pytest.approx(4.0)


def test_tc06_corridor_with_good_fix_is_outside():
    """The credit is capped, so a genuinely distant student is refused."""
    verdict, effective = geofence(55.0, 12.0)
    assert verdict == OUTSIDE
    assert effective == pytest.approx(43.0)


def test_far_away_is_outside():
    verdict, effective = geofence(180.0, 15.0)
    assert verdict == OUTSIDE
    assert effective == pytest.approx(165.0)


def test_tc11_vague_reading_asks_for_retry():
    verdict, effective = geofence(30.0, 90.0)
    assert verdict == RETRY_POOR_ACCURACY
    assert effective is None


# --- Credit cap --------------------------------------------------------

def test_credit_is_capped_at_the_configured_value():
    """A huge accuracy cannot buy unlimited forgiveness.

    Without the cap, accuracy=50 would forgive 50 m and let somebody in
    the next building through.
    """
    verdict, effective = geofence(50.0, 50.0)
    assert verdict == OUTSIDE
    assert effective == pytest.approx(15.0)


def test_boundary_exactly_on_the_radius_is_inside():
    verdict, _ = geofence(10.0, 0.0)
    assert verdict == INSIDE


def test_just_outside_the_radius_is_outside():
    verdict, _ = geofence(10.01, 0.0)
    assert verdict == OUTSIDE


# --- Bad input ---------------------------------------------------------

def test_missing_accuracy_is_a_retry_not_a_pass():
    assert geofence(1.0, None)[0] == RETRY_POOR_ACCURACY


def test_negative_accuracy_is_rejected():
    assert geofence(1.0, -5.0)[0] == RETRY_POOR_ACCURACY


def test_nan_accuracy_is_rejected():
    assert geofence(1.0, float("nan"))[0] == RETRY_POOR_ACCURACY


def test_non_numeric_accuracy_is_rejected():
    assert geofence(1.0, "very good")[0] == RETRY_POOR_ACCURACY


@pytest.mark.parametrize(
    "lat,lon",
    [(0, 0), (90, 180), (-90, -180), (28.6139, 77.2090)],
)
def test_valid_coordinates_accepted(lat, lon):
    assert valid_coordinates(lat, lon)


@pytest.mark.parametrize(
    "lat,lon",
    [
        (91, 0), (-91, 0), (0, 181), (0, -181),
        (None, 0), ("x", 0),
        (float("nan"), 0), (float("inf"), 0),
    ],
)
def test_invalid_coordinates_rejected(lat, lon):
    assert not valid_coordinates(lat, lon)

"""Distance calculation and the accuracy-aware geofence test.

Pure functions with no Flask or database dependency, so the geofence can
be tested directly -- which matters, because this is the piece most
likely to be tuned after walking the actual classroom.
"""

import math

EARTH_RADIUS_M = 6_371_000.0

# Geofence verdicts
INSIDE = "INSIDE"
OUTSIDE = "OUTSIDE"
RETRY_POOR_ACCURACY = "RETRY_POOR_ACCURACY"


def haversine_meters(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points, in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def valid_coordinates(lat, lon):
    """Range check. Rejects NaN and infinity as well as out-of-range."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    if math.isnan(lat) or math.isnan(lon) or math.isinf(lat) or math.isinf(lon):
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def check_geofence(distance, accuracy, radius, accuracy_credit, max_accuracy,
                   anchor_accuracy=None, anchor_credit=0):
    """Decide whether a reading places the student inside the radius.

    A naive ``distance <= radius`` test against a 10 m radius is a coin
    flip: indoor GPS error routinely exceeds 10 m, so a student in the
    front row can read as 25 m away while the phone beside them reads 3 m.

    So the reading is given credit for its own stated error -- the
    browser's ``accuracy`` is the radius of the 68% confidence circle --
    capped so the credit cannot grow without limit. A reading too vague
    to say anything useful is sent back for a retry instead of being
    guessed at.

    When the circle is centred on the teacher's live position rather than
    a surveyed point, the *centre* has error too, and the two errors
    compound: two phones side by side can differ by the sum of their
    uncertainties. ``anchor_accuracy`` is forgiven on top, capped
    separately. Pass None for a surveyed point, which is treated as exact.

    Returns ``(verdict, effective_distance)``. ``effective_distance`` is
    None when the reading was unusable.
    """
    if accuracy is None:
        return RETRY_POOR_ACCURACY, None
    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return RETRY_POOR_ACCURACY, None

    if math.isnan(accuracy) or accuracy < 0 or accuracy > max_accuracy:
        return RETRY_POOR_ACCURACY, None

    credit = min(accuracy, accuracy_credit)

    if anchor_accuracy is not None:
        try:
            anchor_accuracy = float(anchor_accuracy)
            if not math.isnan(anchor_accuracy) and anchor_accuracy > 0:
                credit += min(anchor_accuracy, anchor_credit)
        except (TypeError, ValueError):
            pass

    effective = distance - credit

    if effective <= radius:
        return INSIDE, effective
    return OUTSIDE, effective


def distance_to_location(lat, lon, location):
    """Distance in metres from a reading to a configured classroom."""
    return haversine_meters(lat, lon, location.latitude, location.longitude)


def distance_to_anchor(lat, lon, anchor_lat, anchor_lon):
    """Distance in metres from a reading to the session's geofence centre."""
    return haversine_meters(lat, lon, anchor_lat, anchor_lon)

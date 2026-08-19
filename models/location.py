"""Classroom locations and the networks that serve them."""

from extensions import db
from util import utcnow


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)

    # Float is a C double here, which carries far more precision than the
    # 6+ decimal places a 10 m radius needs. Capture these by standing in
    # the room -- a map pin is not accurate enough at this radius.
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    radius_meters = db.Column(db.Integer, nullable=False, default=10)

    # Comma-separated IPs or CIDRs that the classroom's traffic exits
    # from. Empty means "no network check possible for this location",
    # which the verification chain treats as a failure when the check is
    # enforced, rather than silently skipping it.
    allowed_networks = db.Column(db.String(500), default="")

    # Per-access-point verification. Browsers cannot read a BSSID, so
    # this is only usable from the native app.
    wifi_bssid = db.Column(db.String(64))

    created_at = db.Column(db.DateTime, default=utcnow)

    sessions = db.relationship("AttendanceSession", back_populates="location")

    def network_list(self):
        if not self.allowed_networks:
            return []
        return [n.strip() for n in self.allowed_networks.split(",") if n.strip()]

    def __repr__(self):
        return f"<Location {self.name} r={self.radius_meters}m>"

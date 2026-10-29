from datetime import datetime, timezone

from ..extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Agent(db.Model):
    """Represents a dispatch rider or field agent using a 2G/feature phone."""

    __tablename__ = "agents"

    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    current_tower_id = db.Column(db.String(64), nullable=True)
    registered_cell_tower_id = db.Column(db.String(64), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    total_deliveries = db.Column(db.Integer, default=0)
    total_airtime_earned = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=utc_now)
    deliveries = db.relationship(
        "Delivery",
        primaryjoin="Agent.id == foreign(Delivery.agent_id)",
        back_populates="agent",
        lazy=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phone_number": self.phone_number,
            "current_tower_id": self.current_tower_id,
            "registered_cell_tower_id": self.registered_cell_tower_id,
            "is_active": self.is_active,
            "total_deliveries": self.total_deliveries,
            "total_airtime_earned": self.total_airtime_earned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

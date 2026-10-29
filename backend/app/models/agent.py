from datetime import datetime

from app.extensions import db


class Agent(db.Model):
    """A registered SignalProof field agent / rider (feature-phone user)."""

    __tablename__ = "agents"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    registered_cell_tower_id = db.Column(
        db.String(64), nullable=False
    )  # e.g. "MCC-MNC-LAC-CELLID" of the agent's home zone
    api_key = db.Column(db.String(64), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    deliveries = db.relationship(
        "Delivery", back_populates="agent", lazy=True, cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "phone_number": self.phone_number,
            "name": self.name,
            "registered_cell_tower_id": self.registered_cell_tower_id,
            "api_key": self.api_key,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

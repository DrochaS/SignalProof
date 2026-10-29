import random
import string
from datetime import datetime

from app.extensions import db


class Delivery(db.Model):
    """A delivery/fulfilment job tied to an agent and a destination cell-tower zone."""

    __tablename__ = "deliveries"

    id = db.Column(db.Integer, primary_key=True)
    delivery_code = db.Column(db.String(16), unique=True, nullable=False, index=True)  # e.g. "8020"
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id"), nullable=False)
    buyer_phone = db.Column(db.String(20), nullable=False)
    destination_cell_tower_id = db.Column(db.String(64), nullable=False)
    zone_name = db.Column(db.String(100), nullable=True)
    otp_code = db.Column(db.String(16), nullable=True)
    otp_sent = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending|otp_sent|verified|failed
    delivery_fee = db.Column(db.Integer, default=50, nullable=False)  # KES airtime bonus
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)

    agent = db.relationship("Agent", back_populates="deliveries")
    ussd_sessions = db.relationship(
        "USSDSession", back_populates="delivery", lazy=True, cascade="all, delete-orphan"
    )

    def generate_otp(self, length=4):
        self.otp_code = "".join(random.choices(string.digits, k=length))
        self.otp_sent = False
        self.status = "pending"
        return self.otp_code

    def mark_otp_sent(self):
        self.otp_sent = True
        self.status = "otp_sent"

    def mark_verified(self):
        self.status = "verified"
        self.verified_at = datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "delivery_code": self.delivery_code,
            "agent_id": self.agent_id,
            "buyer_phone": self.buyer_phone,
            "destination_cell_tower_id": self.destination_cell_tower_id,
            "zone_name": self.zone_name,
            "status": self.status,
            "delivery_fee": self.delivery_fee,
            "otp_sent": self.otp_sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


class USSDSession(db.Model):
    """Tracks a USSD session state machine for a feature-phone agent."""

    __tablename__ = "ussd_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), nullable=False)
    state = db.Column(db.String(32), default="start", nullable=False)  # start|awaiting_otp|completed
    delivery_id = db.Column(db.Integer, db.ForeignKey("deliveries.id"), nullable=True)
    observed_cell_tower_id = db.Column(db.String(64), nullable=True)
    network_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    delivery = db.relationship("Delivery", back_populates="ussd_sessions")

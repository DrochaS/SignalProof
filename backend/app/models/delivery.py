import random
from datetime import datetime, timezone
from backend.app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Delivery(db.Model):
    """Represents a fulfillment delivery order protected by SignalProof escrow."""

    __tablename__ = "deliveries"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tracking_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    buyer_name = db.Column(db.String(100), nullable=False)
    buyer_phone = db.Column(db.String(20), nullable=False, index=True)
    agent_id = db.Column(db.String(32), nullable=True, index=True)
    agent_name = db.Column(db.String(100), nullable=True)
    agent_phone = db.Column(db.String(20), nullable=True, index=True)

    package_description = db.Column(db.String(255), default="Parcel Delivery")
    destination_zone = db.Column(db.String(100), default="Westlands Zone")
    destination_tower_id = db.Column(db.String(64), default="TOW-NBO-042")

    # OTP verification
    otp_code = db.Column(db.String(6), nullable=False)
    otp_attempts = db.Column(db.Integer, default=0)

    # Status: PENDING, LOCATION_VERIFIED, OTP_SENT, COMPLETED, FAILED, CANCELLED
    status = db.Column(db.String(32), default="PENDING", index=True)

    # Escrow / Payout details
    payout_amount = db.Column(db.Float, default=50.0)
    currency = db.Column(db.String(10), default="KES")
    airtime_status = db.Column(db.String(32), default="NOT_DISBURSED")
    airtime_transaction_id = db.Column(db.String(100), nullable=True)

    # Telephony message references
    sms_otp_message_id = db.Column(db.String(100), nullable=True)
    sms_receipt_buyer_id = db.Column(db.String(100), nullable=True)
    sms_receipt_agent_id = db.Column(db.String(100), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    verified_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    @classmethod
    def generate_otp(cls) -> str:
        """Generate a secure 4-digit numeric OTP code."""
        return f"{random.randint(1000, 9999)}"

    @classmethod
    def generate_tracking_number(cls) -> str:
        """Generate a human-readable unique tracking number."""
        return f"SP-{datetime.now(timezone.utc).strftime('%y%m')}-{random.randint(10000, 99999)}"

    def to_dict(self) -> dict:
        """Serialize delivery model to dictionary."""
        return {
            "id": self.id,
            "tracking_number": self.tracking_number,
            "buyer_name": self.buyer_name,
            "buyer_phone": self.buyer_phone,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_phone": self.agent_phone,
            "package_description": self.package_description,
            "destination_zone": self.destination_zone,
            "destination_tower_id": self.destination_tower_id,
            "otp_code": self.otp_code,
            "otp_attempts": self.otp_attempts,
            "status": self.status,
            "payout_amount": self.payout_amount,
            "currency": self.currency,
            "airtime_status": self.airtime_status,
            "airtime_transaction_id": self.airtime_transaction_id,
            "sms_otp_message_id": self.sms_otp_message_id,
            "sms_receipt_buyer_id": self.sms_receipt_buyer_id,
            "sms_receipt_agent_id": self.sms_receipt_agent_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

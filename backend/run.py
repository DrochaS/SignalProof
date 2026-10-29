"""Entrypoint to run the SignalProof Backend application."""

import os
from backend.app import create_app
from backend.app.config import Config
from backend.app.extensions import db
from backend.app.models.agent import Agent
from backend.app.models.delivery import Delivery

app = create_app(Config)


def seed_demo_data():
    """Seed initial demo agent and delivery if database is empty."""
    with app.app_context():
        if Agent.query.count() == 0:
            demo_agent = Agent(
                id="AG-001",
                name="Brian Kipkorir",
                phone_number="+254722000111",
                current_tower_id="TOW-NBO-042",
                is_active=True,
            )
            db.session.add(demo_agent)

        if Delivery.query.count() == 0:
            demo_delivery = Delivery(
                tracking_number="SP-2026-DEMO1",
                buyer_name="Alice Wanjiku",
                buyer_phone="+254712345678",
                agent_id="AG-001",
                agent_name="Brian Kipkorir",
                agent_phone="+254722000111",
                package_description="Agricultural Fertilizer (50kg)",
                destination_zone="Westlands Zone",
                destination_tower_id="TOW-NBO-042",
                otp_code="4821",
                status="PENDING",
                payout_amount=50.0,
                currency="KES",
                airtime_status="NOT_DISBURSED",
            )
            db.session.add(demo_delivery)

        db.session.commit()


if __name__ == "__main__":
    seed_demo_data()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)

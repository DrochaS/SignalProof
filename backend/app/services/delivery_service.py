"""Delivery Service for SignalProof.

Coordinates the delivery lifecycle:
1. Delivery Creation & OTP Generation
2. Location Verification (Cell Tower handshake)
3. Automated Buyer OTP Dispatch via Africa's Talking SMS
4. Dual Verification Handshake (OTP match)
5. Instant Escrow Settlement (Airtime payout + Dual SMS receipts)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.app.extensions import db
from backend.app.models.agent import Agent
from backend.app.models.delivery import Delivery
from backend.app.services.africastalking import (
    get_africastalking_service,
    normalize_phone_number,
)

logger = logging.getLogger("signalproof.delivery_service")


class DeliveryService:
    """Business logic coordinator for escrowed deliveries and telephony triggers."""

    def __init__(self, at_service=None):
        self.at_service = at_service or get_africastalking_service()

    def create_delivery(
        self,
        buyer_name: str,
        buyer_phone: str,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        agent_phone: Optional[str] = None,
        package_description: str = "Parcel Delivery",
        destination_zone: str = "Westlands Zone",
        destination_tower_id: str = "TOW-NBO-042",
        payout_amount: float = 50.0,
        currency: str = "KES",
        custom_otp: Optional[str] = None,
    ) -> Delivery:
        """Create a new delivery order with a unique tracking number and 4-digit OTP."""
        normalized_buyer = normalize_phone_number(buyer_phone)
        normalized_agent = normalize_phone_number(agent_phone) if agent_phone else None

        otp_code = custom_otp if custom_otp else Delivery.generate_otp()
        tracking_number = Delivery.generate_tracking_number()

        delivery = Delivery(
            tracking_number=tracking_number,
            buyer_name=buyer_name.strip(),
            buyer_phone=normalized_buyer,
            agent_id=agent_id.strip() if agent_id else None,
            agent_name=agent_name.strip() if agent_name else None,
            agent_phone=normalized_agent,
            package_description=package_description.strip(),
            destination_zone=destination_zone.strip(),
            destination_tower_id=destination_tower_id.strip(),
            otp_code=otp_code,
            status="PENDING",
            payout_amount=float(payout_amount),
            currency=currency.strip().upper(),
            airtime_status="NOT_DISBURSED",
        )

        db.session.add(delivery)

        # Auto-create or ensure agent record exists if agent_id / agent_phone provided
        if agent_id and normalized_agent:
            agent = Agent.query.filter_by(id=agent_id).first()
            if not agent:
                agent = Agent(
                    id=agent_id,
                    name=agent_name or f"Agent {agent_id}",
                    phone_number=normalized_agent,
                    current_tower_id=destination_tower_id,
                )
                db.session.add(agent)

        db.session.commit()
        logger.info(
            "Created delivery #%s (%s) for buyer %s with OTP %s",
            delivery.id,
            delivery.tracking_number,
            delivery.buyer_phone,
            delivery.otp_code,
        )
        return delivery

    def get_delivery(self, delivery_id_or_tracking: Union[int, str]) -> Optional[Delivery]:
        """Find a delivery by numeric ID or tracking number string."""
        if isinstance(delivery_id_or_tracking, int) or (
            isinstance(delivery_id_or_tracking, str) and delivery_id_or_tracking.isdigit()
        ):
            return db.session.get(Delivery, int(delivery_id_or_tracking))
        return Delivery.query.filter_by(tracking_number=str(delivery_id_or_tracking)).first()

    def list_deliveries(
        self,
        status: Optional[str] = None,
        agent_phone: Optional[str] = None,
        buyer_phone: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Delivery], int]:
        """Query and paginate deliveries with optional filters."""
        query = Delivery.query

        if status:
            query = query.filter_by(status=status.upper())
        if agent_phone:
            norm_agent = normalize_phone_number(agent_phone)
            query = query.filter_by(agent_phone=norm_agent)
        if buyer_phone:
            norm_buyer = normalize_phone_number(buyer_phone)
            query = query.filter_by(buyer_phone=norm_buyer)

        total = query.count()
        deliveries = (
            query.order_by(Delivery.created_at.desc()).offset(offset).limit(limit).all()
        )
        return deliveries, total

    def trigger_otp_dispatch(
        self,
        delivery_id: Union[int, str],
        cell_tower_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify location and automatically dispatch OTP SMS to the buyer.

        Triggered when agent arrives at destination and dials USSD or confirms arrival.
        """
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return {"success": False, "error": f"Delivery '{delivery_id}' not found"}

        # Optional tower match verification
        if cell_tower_id and delivery.destination_tower_id:
            if cell_tower_id.strip() != delivery.destination_tower_id.strip():
                delivery.status = "FAILED"
                db.session.commit()
                return {
                    "success": False,
                    "error": f"Location Mismatch: Active tower {cell_tower_id} does not match drop-off tower {delivery.destination_tower_id}",
                    "status": "LOCATION_MISMATCH",
                }

        delivery.status = "LOCATION_VERIFIED"
        delivery.verified_at = datetime.now(timezone.utc)

        # Trigger Africa's Talking SMS OTP dispatch to Buyer
        sms_result = self.at_service.send_otp_sms(
            buyer_phone=delivery.buyer_phone,
            otp_code=delivery.otp_code,
            delivery_id=delivery.id,
            zone_name=delivery.destination_zone,
        )

        if sms_result.get("success"):
            delivery.status = "OTP_SENT"
            message_ids = sms_result.get("message_ids", [])
            if message_ids:
                delivery.sms_otp_message_id = message_ids[0]

        db.session.commit()

        return {
            "success": True,
            "delivery": delivery.to_dict(),
            "sms_dispatch": sms_result,
            "message": "Buyer OTP dispatched successfully via SMS",
        }

    def verify_otp_and_settle(
        self,
        delivery_id: Union[int, str],
        submitted_otp: str,
    ) -> Dict[str, Any]:
        """Verify submitted 4-digit OTP.

        Upon match:
        - Marks delivery COMPLETED
        - Executes instant Airtime disbursement to agent SIM
        - Sends dual SMS receipts (Buyer escrow release & Agent payout confirmation)
        """
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return {"success": False, "error": f"Delivery '{delivery_id}' not found"}

        if delivery.status == "COMPLETED":
            return {
                "success": False,
                "error": "Delivery has already been completed and escrow released",
                "delivery": delivery.to_dict(),
            }

        clean_otp = str(submitted_otp).strip()
        delivery.otp_attempts = (delivery.otp_attempts or 0) + 1

        if clean_otp != delivery.otp_code.strip():
            db.session.commit()
            return {
                "success": False,
                "error": "Invalid OTP code",
                "otp_attempts": delivery.otp_attempts,
                "delivery": delivery.to_dict(),
            }

        # OTP verified! Mark completed
        now = datetime.now(timezone.utc)
        delivery.status = "COMPLETED"
        if not delivery.verified_at:
            delivery.verified_at = now
        delivery.completed_at = now

        # 1. Trigger Airtime Disbursement to Agent SIM
        airtime_result = {}
        if delivery.agent_phone and delivery.payout_amount > 0:
            airtime_result = self.at_service.disburse_agent_payout(
                agent_phone=delivery.agent_phone,
                amount=delivery.payout_amount,
                currency=delivery.currency,
                delivery_id=delivery.id,
            )
            if airtime_result.get("success"):
                delivery.airtime_status = "DISBURSED"
                delivery.airtime_transaction_id = airtime_result.get("transaction_id")
            else:
                delivery.airtime_status = "FAILED"
        else:
            delivery.airtime_status = "SKIPPED_NO_AGENT_PHONE"

        # 2. Trigger Dual SMS Receipts
        receipt_result = {}
        if delivery.buyer_phone and delivery.agent_phone:
            receipt_result = self.at_service.send_delivery_receipt_sms(
                buyer_phone=delivery.buyer_phone,
                agent_phone=delivery.agent_phone,
                delivery_id=delivery.id,
                airtime_amount=delivery.payout_amount,
                currency=delivery.currency,
            )
            buyer_msg_ids = receipt_result.get("buyer_receipt", {}).get("message_ids", [])
            agent_msg_ids = receipt_result.get("agent_receipt", {}).get("message_ids", [])
            if buyer_msg_ids:
                delivery.sms_receipt_buyer_id = buyer_msg_ids[0]
            if agent_msg_ids:
                delivery.sms_receipt_agent_id = agent_msg_ids[0]

        # 3. Update Agent Statistics
        if delivery.agent_id:
            agent = Agent.query.filter_by(id=delivery.agent_id).first()
            if agent:
                agent.total_deliveries = (agent.total_deliveries or 0) + 1
                if delivery.airtime_status == "DISBURSED":
                    agent.total_airtime_earned = (
                        agent.total_airtime_earned or 0.0
                    ) + delivery.payout_amount

        db.session.commit()

        logger.info(
            "Delivery #%s successfully verified and settled. Escrow released. Airtime: %s",
            delivery.id,
            delivery.airtime_status,
        )

        return {
            "success": True,
            "message": "Delivery verified successfully. Escrow released and airtime disbursed.",
            "delivery": delivery.to_dict(),
            "airtime_payout": airtime_result,
            "sms_receipts": receipt_result,
        }

    def trigger_airtime_disbursement(
        self,
        delivery_id: Union[int, str],
        amount: Optional[float] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Disburse or re-disburse airtime payout for a delivery."""
        delivery = self.get_delivery(delivery_id)
        if not delivery:
            return {"success": False, "error": f"Delivery '{delivery_id}' not found"}

        if not delivery.agent_phone:
            return {
                "success": False,
                "error": "Cannot disburse airtime: agent_phone is not set",
            }

        payout_amount = float(amount) if amount is not None else delivery.payout_amount
        payout_currency = currency or delivery.currency

        airtime_result = self.at_service.disburse_agent_payout(
            agent_phone=delivery.agent_phone,
            amount=payout_amount,
            currency=payout_currency,
            delivery_id=delivery.id,
        )

        if airtime_result.get("success"):
            delivery.airtime_status = "DISBURSED"
            delivery.airtime_transaction_id = airtime_result.get("transaction_id")
            db.session.commit()

        return {
            "success": airtime_result.get("success", False),
            "delivery_id": delivery.id,
            "agent_phone": delivery.agent_phone,
            "payout": airtime_result,
        }


# Module singleton
_delivery_service_instance: Optional[DeliveryService] = None


def get_delivery_service() -> DeliveryService:
    global _delivery_service_instance
    if _delivery_service_instance is None:
        _delivery_service_instance = DeliveryService()
    return _delivery_service_instance

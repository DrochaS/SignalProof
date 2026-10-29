"""Delivery Service for SignalProof.

Coordinates the delivery lifecycle:
1. Delivery Creation & OTP Generation
2. Location Verification (Cell Tower handshake)
3. Automated Buyer OTP Dispatch via Africa's Talking SMS
4. Dual Verification Handshake (OTP match)
5. Instant Escrow Settlement (Airtime payout + Dual SMS receipts)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import current_app, has_app_context

from ..extensions import db
from ..models.agent import Agent
from ..models.delivery import Delivery, USSDSession
from .africastalking import (
    get_africastalking_service,
    normalize_phone_number,
)

logger = logging.getLogger("signalproof.delivery_service")
STATE_START = "start"
STATE_AWAITING_OTP = "awaiting_otp"
STATE_COMPLETED = "completed"


def _normalize_tower(tower_id: Optional[str]) -> Optional[str]:
    if not tower_id:
        return None
    return str(tower_id).strip().upper().rsplit("-", 1)[-1]


def _towers_match(observed: Optional[str], expected: Optional[str]) -> bool:
    observed_id = _normalize_tower(observed)
    expected_id = _normalize_tower(expected)
    return bool(observed_id and expected_id and observed_id == expected_id)


def _get_or_create_ussd_session(session_id: str, phone_number: str) -> USSDSession:
    session = USSDSession.query.filter_by(session_id=session_id).first()
    if session is None:
        session = USSDSession(
            session_id=session_id,
            phone_number=phone_number,
            state=STATE_START,
        )
        db.session.add(session)
        db.session.commit()
    else:
        if session.phone_number != phone_number:
            raise ValueError("USSD session is associated with a different phone number")
        ttl_minutes = (
            current_app.config.get("SESSION_TTL_MINUTES", 10)
            if has_app_context()
            else 10
        )
        updated_at = session.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if updated_at < datetime.now(timezone.utc) - timedelta(minutes=ttl_minutes):
            session.state = STATE_START
            session.delivery_id = None
            session.network_verified = False
            session.observed_cell_tower_id = None
            db.session.commit()
    return session


class DeliveryService:
    """Business logic coordinator for escrowed deliveries and telephony triggers."""

    def __init__(self, at_service=None):
        self.at_service = at_service or (
            current_app.extensions.get("signalproof_at_service")
            if has_app_context()
            else None
        ) or get_africastalking_service()
        self.at = self.at_service

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
        delivery_code: Optional[str] = None,
        destination_cell_tower_id: Optional[str] = None,
        zone_name: Optional[str] = None,
        delivery_fee: Optional[int] = None,
    ) -> Delivery:
        """Create a new delivery order with a unique tracking number and 4-digit OTP."""
        normalized_buyer = normalize_phone_number(buyer_phone)
        normalized_agent = normalize_phone_number(agent_phone) if agent_phone else None

        otp_code = custom_otp if custom_otp else Delivery.generate_otp()
        tracking_number = Delivery.generate_tracking_number()
        if agent_id and normalized_agent is None:
            existing_agent = Agent.query.filter_by(id=agent_id).first()
            if existing_agent:
                normalized_agent = existing_agent.phone_number

        if delivery_code is None:
            delivery_code = Delivery.generate_delivery_code()
            while Delivery.query.filter_by(delivery_code=delivery_code).first():
                delivery_code = Delivery.generate_delivery_code()

        tower_id = (destination_cell_tower_id or destination_tower_id).strip()
        resolved_zone = (zone_name or destination_zone).strip()

        delivery = Delivery(
            delivery_code=delivery_code,
            tracking_number=tracking_number,
            buyer_name=buyer_name.strip(),
            buyer_phone=normalized_buyer,
            agent_id=agent_id.strip() if agent_id else None,
            agent_name=agent_name.strip() if agent_name else None,
            agent_phone=normalized_agent,
            package_description=package_description.strip(),
            destination_zone=resolved_zone,
            destination_tower_id=tower_id,
            destination_cell_tower_id=tower_id,
            zone_name=resolved_zone,
            otp_code=otp_code,
            status="PENDING",
            payout_amount=float(payout_amount),
            currency=currency.strip().upper(),
            airtime_status="NOT_DISBURSED",
            delivery_fee=int(
                delivery_fee
                if delivery_fee is not None
                else (
                    current_app.config.get("DELIVERY_FEE_DEFAULT", payout_amount)
                    if has_app_context()
                    else payout_amount
                )
            ),
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
                    registered_cell_tower_id=destination_tower_id,
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
        """Find a delivery by numeric ID, tracking number, or USSD delivery code."""
        if isinstance(delivery_id_or_tracking, int) or (
            isinstance(delivery_id_or_tracking, str) and delivery_id_or_tracking.isdigit()
        ):
            delivery = db.session.get(Delivery, int(delivery_id_or_tracking))
            if delivery is not None:
                return delivery
        identifier = str(delivery_id_or_tracking)
        return Delivery.query.filter(
            db.or_(
                Delivery.tracking_number == identifier,
                Delivery.delivery_code == identifier,
            )
        ).first()

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

    def handle_ussd(
        self, session_id: str, phone_number: str, text: str
    ) -> str:
        """Drive the delivery-code, location, and OTP USSD state machine."""
        normalized_phone = normalize_phone_number(phone_number)
        session = _get_or_create_ussd_session(session_id, normalized_phone)
        agent = Agent.query.filter_by(
            phone_number=normalized_phone, is_active=True
        ).first()
        if agent is None:
            return self._ussd_end(
                "Unregistered number.\n"
                "This line is not registered as a SignalProof agent."
            )

        text = (text or "").strip()
        if session.state == STATE_START:
            return self._handle_ussd_start(session, agent, text)
        if session.state == STATE_AWAITING_OTP:
            return self._handle_ussd_otp(session, text)
        return self._ussd_end(
            "Session already completed.\nDial *384*# again for a new delivery."
        )

    def _handle_ussd_start(self, session, agent, delivery_code: str) -> str:
        if not delivery_code:
            return self._ussd_continue("SignalProof USSD\nEnter Delivery Code:")

        delivery = Delivery.query.filter_by(delivery_code=delivery_code).first()
        if delivery is None:
            return self._ussd_end("Invalid Delivery Code.\nTry again or contact dispatch.")
        if delivery.agent_id != agent.id:
            return self._ussd_end("Delivery not assigned to this agent.")
        if delivery.status not in ("PENDING", "OTP_SENT"):
            return self._ussd_end(f"Delivery already {delivery.status}.")

        try:
            tower_info = self.at_service.get_cell_tower(agent.phone_number)
        except Exception:
            logger.exception("Network telemetry failed for agent %s", agent.id)
            return self._ussd_end(
                "Network verification unavailable.\nTry again shortly."
            )

        observed_tower = tower_info.get("cell_tower_id")
        expected_tower = (
            delivery.destination_cell_tower_id or delivery.destination_tower_id
        )
        session.observed_cell_tower_id = observed_tower
        session.delivery_id = delivery.id
        if not _towers_match(observed_tower, expected_tower):
            session.network_verified = False
            db.session.commit()
            return self._ussd_end(
                "Location Mismatch\n"
                "Agent outside drop-off radius.\n"
                f"Observed: {observed_tower}\nExpected: {expected_tower}"
            )

        session.network_verified = True
        delivery.verified_at = datetime.now(timezone.utc)
        delivery.status = "LOCATION_VERIFIED"
        sms_result = self.at_service.send_otp_sms(
            buyer_phone=delivery.buyer_phone,
            otp_code=delivery.otp_code,
            delivery_id=delivery.id,
            zone_name=delivery.destination_zone,
        )
        if not sms_result.get("success"):
            db.session.commit()
            logger.error(
                "USSD OTP dispatch failed for delivery %s: %s",
                delivery.id,
                sms_result.get("error", "unknown error"),
            )
            return self._ussd_end(
                "Could not send buyer OTP.\nPlease contact dispatch."
            )

        delivery.status = "OTP_SENT"
        delivery.otp_sent = True
        message_ids = sms_result.get("message_ids", [])
        if message_ids:
            delivery.sms_otp_message_id = message_ids[0]
        session.state = STATE_AWAITING_OTP
        db.session.commit()
        zone = delivery.zone_name or delivery.destination_zone or expected_tower
        otp_length = current_app.config.get("OTP_LENGTH", 4)
        return self._ussd_continue(
            f"Location Verified: {zone}\n"
            f"Enter Buyer's {otp_length}-digit OTP:"
        )

    def _handle_ussd_otp(self, session, submitted_otp: str) -> str:
        delivery = (
            db.session.get(Delivery, session.delivery_id)
            if session.delivery_id is not None
            else None
        )
        if delivery is None:
            return self._ussd_end("Session delivery not found.\nStart a new session.")
        if (
            not submitted_otp.isdigit()
            or len(submitted_otp)
            != (
                current_app.config.get("OTP_LENGTH", 4)
                if has_app_context()
                else 4
            )
        ):
            return self._ussd_continue("Invalid OTP\nEnter Buyer's 4-digit OTP:")

        if delivery.status != "OTP_SENT":
            return self._ussd_end("Buyer OTP has not been dispatched for this delivery.")
        if not session.network_verified:
            return self._ussd_end("Network verification required.\nStart a new session.")
        result = self.verify_otp_and_settle(delivery.id, submitted_otp)
        if not result.get("success"):
            if result.get("error") == "Invalid OTP code":
                return self._ussd_continue(
                    "Incorrect OTP\nEnter Buyer's 4-digit OTP:"
                )
            return self._ussd_end(result.get("error", "Delivery verification failed."))

        session.state = STATE_COMPLETED
        db.session.commit()
        return self._ussd_end(
            f"Delivery Verified!\nEscrow released.\n"
            f"{delivery.currency} {delivery.payout_amount:.0f} sent to "
            f"{session.phone_number}."
        )

    @staticmethod
    def _ussd_continue(message: str) -> str:
        return f"CON {message}"

    @staticmethod
    def _ussd_end(message: str) -> str:
        return f"END {message}"

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
        expected_tower = (
            delivery.destination_cell_tower_id or delivery.destination_tower_id
        )
        if cell_tower_id and expected_tower:
            if not _towers_match(cell_tower_id, expected_tower):
                delivery.status = "FAILED"
                db.session.commit()
                return {
                    "success": False,
                    "error": f"Location Mismatch: Active tower {cell_tower_id} does not match drop-off tower {expected_tower}",
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
            delivery.otp_sent = True
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
    if has_app_context():
        app_service = current_app.extensions.get("signalproof_delivery_service")
        if app_service is None:
            app_service = DeliveryService(
                at_service=current_app.extensions.get("signalproof_at_service")
            )
            current_app.extensions["signalproof_delivery_service"] = app_service
        return app_service
    if _delivery_service_instance is None:
        _delivery_service_instance = DeliveryService()
    return _delivery_service_instance

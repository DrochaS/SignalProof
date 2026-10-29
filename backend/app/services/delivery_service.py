import logging

from flask import current_app

from app.config import Config
from app.extensions import db
from app.models.delivery import Delivery, USSDSession
from app.models.agent import Agent
from app.services.africastalking import AfricasTalkingService

logger = logging.getLogger(__name__)

# USSD state-machine states
STATE_START = "start"
STATE_AWAITING_OTP = "awaiting_otp"
STATE_COMPLETED = "completed"


def normalize_tower(tower_id):
    """Normalise a cell-tower id to its cell-id portion for comparison."""
    if not tower_id:
        return None
    return str(tower_id).strip().upper().rsplit("-", 1)[-1]


def towers_match(observed, expected):
    return normalize_tower(observed) == normalize_tower(expected)


def get_or_create_session(session_id, phone_number):
    session = USSDSession.query.filter_by(session_id=session_id).first()
    if session is None:
        session = USSDSession(
            session_id=session_id,
            phone_number=phone_number,
            state=STATE_START,
        )
        db.session.add(session)
        db.session.commit()
    return session


def find_agent(phone_number):
    return Agent.query.filter_by(phone_number=phone_number, is_active=True).first()


def find_delivery_by_code(delivery_code):
    return Delivery.query.filter_by(delivery_code=delivery_code).first()


class DeliveryService:
    def __init__(self, at_service=None):
        if at_service is None:
            # Prefer the app-wired service (configured with credentials/mock/tower);
            # fall back to a standalone instance outside a request context.
            at_service = getattr(current_app, "at_service", None) or AfricasTalkingService()
        self.at = at_service

    # ---- Public entry point used by the USSD callback ----
    def handle_ussd(self, session_id, phone_number, text):
        session = get_or_create_session(session_id, phone_number)
        text = (text or "").strip()

        # Agent registration gate: only registered agents may use the USSD line.
        agent = find_agent(phone_number)
        if agent is None:
            return self._end(
                "Unregistered number.\n"
                "This line is not registered as a SignalProof agent."
            )

        if session.state == STATE_START:
            return self._handle_start(session, agent, text)
        if session.state == STATE_AWAITING_OTP:
            return self._handle_otp_input(session, text)
        return self._end("Session already completed.\nDial *384*# again for a new delivery.")

    # ---- STATE_START: collect delivery code, verify network, send buyer OTP ----
    def _handle_start(self, session, agent, text):
        if not text:
            return self._cont("SignalProof USSD\nEnter Delivery Code:")

        delivery = find_delivery_by_code(text)
        if delivery is None:
            return self._end("Invalid Delivery Code.\nTry again or contact dispatch.")
        if delivery.agent_id != agent.id:
            return self._end("Delivery not assigned to this agent.")
        if delivery.status not in ("pending", "otp_sent"):
            return self._end(f"Delivery already {delivery.status}.")

        # Network telemetry validation: agent must be on the destination cell tower.
        try:
            tower_info = self.at.get_cell_tower(agent.phone_number)
        except Exception:  # noqa: BLE001 - surface a friendly USSD error
            logger.exception("network telemetry error")
            return self._end("Network verification unavailable.\nTry again shortly.")

        observed = tower_info.get("cell_tower_id")
        session.observed_cell_tower_id = observed
        session.delivery_id = delivery.id

        if not towers_match(observed, delivery.destination_cell_tower_id):
            session.network_verified = False
            db.session.commit()
            return self._end(
                "Location Mismatch\n"
                "Agent outside drop-off radius.\n"
                f"Observed: {observed}\nExpected: {delivery.destination_cell_tower_id}"
            )

        # Location verified: generate OTP and SMS it to the buyer.
        session.network_verified = True
        delivery.generate_otp(length=Config.OTP_LENGTH)
        delivery.mark_otp_sent()
        db.session.commit()

        otp_message = (
            f"SignalProof: Agent is on site. "
            f"Your delivery verification code is {delivery.otp_code}."
        )
        try:
            self.at.send_sms(delivery.buyer_phone, otp_message)
        except Exception:  # noqa: BLE001
            logger.exception("failed to send OTP SMS to buyer")

        session.state = STATE_AWAITING_OTP
        db.session.commit()
        zone = delivery.zone_name or delivery.destination_cell_tower_id
        return self._cont(
            f"Location Verified: {zone}\n"
            f"Enter Buyer's 4-digit OTP:"
        )

    # ---- STATE_AWAITING_OTP: verify OTP, release escrow ----
    def _handle_otp_input(self, session, text):
        delivery = (
            Delivery.query.get(session.delivery_id) if session.delivery_id else None
        )
        if delivery is None:
            return self._end("Session delivery not found.\nStart a new session.")

        if not text.isdigit() or len(text) != Config.OTP_LENGTH:
            return self._cont(f"Invalid OTP\nEnter Buyer's {Config.OTP_LENGTH}-digit OTP:")

        if text != delivery.otp_code:
            return self._cont("Incorrect OTP\nEnter Buyer's 4-digit OTP:")

        # OTP verified: mark delivery and release escrow (airtime + SMS receipts).
        self._release_escrow(session, delivery)

        session.state = STATE_COMPLETED
        db.session.commit()
        return self._end(
            f"Delivery Verified!\n"
            f"Escrow released.\n"
            f"KES {delivery.delivery_fee} sent to {session.phone_number}."
        )

    def _release_escrow(self, session, delivery):
        delivery.mark_verified()
        db.session.commit()

        fee = delivery.delivery_fee
        agent_phone = session.phone_number

        # SMS receipt to agent
        try:
            self.at.send_sms(
                agent_phone,
                f"SignalProof: Delivery verified at {delivery.zone_name or 'site'}. "
                f"Escrow released. KES {fee} disbursed to your SIM.",
            )
        except Exception:  # noqa: BLE001
            logger.exception("agent receipt SMS failed")

        # SMS receipt to buyer
        try:
            self.at.send_sms(
                delivery.buyer_phone,
                f"SignalProof: Delivery confirmed. Escrow released to agent. Thank you!",
            )
        except Exception:  # noqa: BLE001
            logger.exception("buyer receipt SMS failed")

        # Airtime / mobile money payout to the rider's SIM
        try:
            self.at.disburse_airtime(agent_phone, fee, currency_code=Config.CURRENCY_CODE)
        except Exception:  # noqa: BLE001
            logger.exception("airtime disbursement failed")

    @staticmethod
    def _cont(message):
        """CON = keep USSD session open."""
        return f"CON {message}"

    @staticmethod
    def _end(message):
        """END = close USSD session."""
        return f"END {message}"

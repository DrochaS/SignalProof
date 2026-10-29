"""USSD routes for SignalProof.

Provides the entrypoint for Africa's Talking USSD callbacks (*384*8020#).
Enables feature-phone agents to perform presence handshakes and submit buyer OTPs.
"""

import logging
from flask import Blueprint, Response, request
from backend.app.services.delivery_service import get_delivery_service

logger = logging.getLogger("signalproof.ussd")

ussd_bp = Blueprint("ussd", __name__)


@ussd_bp.route("/ussd", methods=["POST", "GET"])
def ussd_callback():
    """Africa's Talking USSD Callback Handler.

    Expected AT parameters:
    - sessionId
    - serviceCode
    - phoneNumber
    - text
    - networkCode
    """
    session_id = request.values.get("sessionId", "")
    service_code = request.values.get("serviceCode", "")
    phone_number = request.values.get("phoneNumber", "")
    text = request.values.get("text", "").strip()

    logger.info(
        "USSD Callback received: session=%s, phone=%s, text='%s'",
        session_id,
        phone_number,
        text,
    )

    delivery_svc = get_delivery_service()

    if not text:
        # Initial screen: Dial *384*#
        response_text = (
            "CON Welcome to SignalProof\n"
            "1. Confirm Drop-off Arrival\n"
            "2. Enter Buyer Delivery OTP\n"
            "3. Check My Payout Balance"
        )
    elif text == "1":
        # Handshake: Agent confirms arrival at site
        # Query active pending delivery for this agent phone
        deliveries, _ = delivery_svc.list_deliveries(
            status="PENDING", agent_phone=phone_number, limit=1
        )
        if deliveries:
            delivery = deliveries[0]
            # Verify and dispatch OTP SMS to buyer
            delivery_svc.trigger_otp_dispatch(delivery.id)
            response_text = (
                f"CON Location Verified: {delivery.destination_zone}\n"
                f"Buyer has been sent a 4-digit OTP via SMS.\n"
                "Enter Buyer's 4-digit OTP:"
            )
        else:
            response_text = "END No pending deliveries found for this agent number."
    elif text.startswith("1*"):
        # Agent entered OTP directly after step 1
        submitted_otp = text.split("*")[-1]
        deliveries, _ = delivery_svc.list_deliveries(
            status="OTP_SENT", agent_phone=phone_number, limit=1
        )
        if deliveries:
            delivery = deliveries[0]
            result = delivery_svc.verify_otp_and_settle(delivery.id, submitted_otp)
            if result.get("success"):
                response_text = (
                    f"END Delivery #{delivery.id} Verified!\n"
                    f"KES {delivery.payout_amount:.0f} airtime payout has been credited to your SIM."
                )
            else:
                response_text = "END Invalid OTP. Please verify with buyer and try again."
        else:
            response_text = "END No active OTP-pending delivery found."
    elif text == "2":
        response_text = "CON Enter Buyer's 4-digit OTP:"
    elif text.startswith("2*"):
        submitted_otp = text.split("*")[-1]
        deliveries, _ = delivery_svc.list_deliveries(
            status="OTP_SENT", agent_phone=phone_number, limit=1
        )
        if deliveries:
            delivery = deliveries[0]
            result = delivery_svc.verify_otp_and_settle(delivery.id, submitted_otp)
            if result.get("success"):
                response_text = (
                    f"END Delivery #{delivery.id} Verified!\n"
                    f"KES {delivery.payout_amount:.0f} airtime payout credited to your SIM."
                )
            else:
                response_text = "END Invalid OTP code. Delivery verification failed."
        else:
            response_text = "END No pending verification found."
    elif text == "3":
        response_text = (
            f"END SignalProof Balance:\n"
            f"Active SIM: {phone_number}\n"
            "Airtime payouts disburse instantly upon delivery completion."
        )
    else:
        response_text = "END Invalid option. Please dial *384*8020# again."

    return Response(response_text, mimetype="text/plain")

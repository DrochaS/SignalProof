import logging

from flask import Blueprint, Response, request

from ..services.delivery_service import get_delivery_service

logger = logging.getLogger("signalproof.ussd")

ussd_bp = Blueprint("ussd", __name__)


@ussd_bp.route("/ussd", methods=["POST", "GET"])
@ussd_bp.route("/ussd/callback", methods=["POST", "GET"])
def ussd_callback():
    """Run the delivery-code and network-verified USSD state machine."""
    session_id = request.values.get("sessionId", "")
    phone_number = request.values.get("phoneNumber", "")
    text = request.values.get("text", "")
    if not session_id or not phone_number:
        return Response(
            "END Missing required USSD parameters.\n",
            status=400,
            mimetype="text/plain",
        )

    try:
        response_text = get_delivery_service().handle_ussd(
            session_id=session_id,
            phone_number=phone_number,
            text=text,
        )
    except Exception:
        logger.exception("USSD callback failed for session %s", session_id)
        response_text = "END Service unavailable.\nPlease try again later."
    return Response(response_text, mimetype="text/plain")

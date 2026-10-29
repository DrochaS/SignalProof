import logging
from flask import Blueprint, request, jsonify

from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)

ussd_bp = Blueprint("ussd", __name__, url_prefix="")


@ussd_bp.route("/ussd/callback", methods=["POST", "GET"])
def ussd_callback():
    """AfricasTalking USSD callback endpoint.

    Accepts form fields (POST) or query args (GET for local testing):
      sessionId, serviceCode, phoneNumber, text

    Returns plain text prefixed with CON (continue session) or END (close session).
    """
    if request.method == "POST":
        session_id = request.form.get("sessionId", "")
        service_code = request.form.get("serviceCode", "")
        phone_number = request.form.get("phoneNumber", "")
        text = request.form.get("text", "")
    else:
        session_id = request.args.get("sessionId", "")
        service_code = request.args.get("serviceCode", "")
        phone_number = request.args.get("phoneNumber", "")
        text = request.args.get("text", "")

    if not session_id or not phone_number:
        return (
            "END Missing required USSD parameters.\n",
            400,
            {"Content-Type": "text/plain"},
        )

    try:
        service = DeliveryService()
        response_text = service.handle_ussd(session_id, phone_number, text)
    except Exception:  # noqa: BLE001 - never break the USSD session with a 500
        logger.exception("USSD callback failed for session %s", session_id)
        response_text = "END Service unavailable.\nPlease try again later."

    return response_text, 200, {"Content-Type": "text/plain"}

"""REST API routes for SignalProof.

Endpoints:
- GET    /api/deliveries                    List deliveries (with filtering & pagination)
- POST   /api/deliveries                    Create new delivery and generate OTP
- GET    /api/deliveries/<id>               Fetch delivery details
- POST   /api/deliveries/<id>/send-otp      Trigger SMS OTP dispatch to buyer
- POST   /api/deliveries/<id>/verify-otp    Verify OTP -> Escrow Release & Airtime Payout
- POST   /api/deliveries/<id>/disburse-airtime Trigger/retry airtime payout
- POST   /api/telephony/send-sms            Africa's Talking SMS test/direct dispatch
- POST   /api/telephony/send-airtime        Africa's Talking Airtime test/direct payout
- GET    /api/telephony/status              Africa's Talking integration & balance status
- GET    /api/stats                         Overall delivery and payout statistics
- GET    /api/health                        Service health probe
"""

import logging
from flask import Blueprint, jsonify, request
from backend.app.models.delivery import Delivery
from backend.app.services.africastalking import (
    get_africastalking_service,
    normalize_phone_number,
)
from backend.app.services.delivery_service import get_delivery_service
from backend.app.extensions import db

logger = logging.getLogger("signalproof.api")

api_bp = Blueprint("api", __name__, url_prefix="/api")


# --------------------------------------------------------------------------
# HEALTH & TELEPHONY STATUS
# --------------------------------------------------------------------------

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "service": "SignalProof Backend",
            "version": "1.0.0",
        }
    ), 200


@api_bp.route("/telephony/status", methods=["GET"])
def telephony_status():
    """Check Africa's Talking integration status, balance, and mode."""
    at_service = get_africastalking_service()
    status_info = at_service.get_account_status()
    return jsonify(status_info), 200


# --------------------------------------------------------------------------
# DELIVERIES CRUD & LIFECYCLE
# --------------------------------------------------------------------------

@api_bp.route("/deliveries", methods=["GET"])
def list_deliveries():
    """List deliveries with optional filtering by status, agent, or buyer."""
    status = request.args.get("status")
    agent_phone = request.args.get("agent_phone")
    buyer_phone = request.args.get("buyer_phone")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    delivery_svc = get_delivery_service()
    deliveries, total = delivery_svc.list_deliveries(
        status=status,
        agent_phone=agent_phone,
        buyer_phone=buyer_phone,
        limit=limit,
        offset=offset,
    )

    return jsonify(
        {
            "total": total,
            "limit": limit,
            "offset": offset,
            "deliveries": [d.to_dict() for d in deliveries],
        }
    ), 200


@api_bp.route("/deliveries", methods=["POST"])
def create_delivery():
    """Create a new delivery protected by SignalProof escrow."""
    data = request.get_json() or {}

    buyer_name = data.get("buyer_name")
    buyer_phone = data.get("buyer_phone")

    if not buyer_name or not buyer_phone:
        return jsonify(
            {
                "success": False,
                "error": "Missing required fields: buyer_name and buyer_phone",
            }
        ), 400

    try:
        delivery_svc = get_delivery_service()
        delivery = delivery_svc.create_delivery(
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            agent_id=data.get("agent_id"),
            agent_name=data.get("agent_name"),
            agent_phone=data.get("agent_phone"),
            package_description=data.get("package_description", "Parcel Delivery"),
            destination_zone=data.get("destination_zone", "Westlands Zone"),
            destination_tower_id=data.get("destination_tower_id", "TOW-NBO-042"),
            payout_amount=float(data.get("payout_amount", 50.0)),
            currency=data.get("currency", "KES"),
            custom_otp=data.get("otp_code"),
        )

        return jsonify(
            {
                "success": True,
                "message": "Delivery created successfully",
                "delivery": delivery.to_dict(),
            }
        ), 201

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Failed to create delivery: %s", str(e))
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api_bp.route("/deliveries/<delivery_id>", methods=["GET"])
def get_delivery(delivery_id):
    """Get single delivery details by numeric ID or tracking number."""
    delivery_svc = get_delivery_service()
    delivery = delivery_svc.get_delivery(delivery_id)

    if not delivery:
        return jsonify(
            {"success": False, "error": f"Delivery '{delivery_id}' not found"}
        ), 404

    return jsonify({"success": True, "delivery": delivery.to_dict()}), 200


@api_bp.route("/deliveries/<delivery_id>/send-otp", methods=["POST"])
def send_otp(delivery_id):
    """Trigger Africa's Talking SMS OTP dispatch to the buyer.

    Accepts optional {"cell_tower_id": "TOW-NBO-042"} in JSON body to verify
    cell-tower radius presence prior to dispatching OTP.
    """
    data = request.get_json(silent=True) or {}
    cell_tower_id = data.get("cell_tower_id")

    delivery_svc = get_delivery_service()
    result = delivery_svc.trigger_otp_dispatch(
        delivery_id=delivery_id,
        cell_tower_id=cell_tower_id,
    )

    if not result.get("success"):
        status_code = 404 if "not found" in result.get("error", "").lower() else 400
        return jsonify(result), status_code

    return jsonify(result), 200


@api_bp.route("/deliveries/<delivery_id>/verify-otp", methods=["POST"])
def verify_otp(delivery_id):
    """Verify 4-digit OTP submitted by Agent via USSD or Web.

    Upon successful verification:
    1. Delivery status changes to COMPLETED
    2. Airtime payout bonus (e.g. KES 50) is disbursed to agent SIM via AT Airtime API
    3. Dual SMS receipts are sent to Buyer (escrow release) and Agent (payout credited)
    """
    data = request.get_json(silent=True) or {}
    otp_code = data.get("otp_code") or data.get("otp")

    if not otp_code:
        return jsonify(
            {"success": False, "error": "Missing required field: otp_code"}
        ), 400

    delivery_svc = get_delivery_service()
    result = delivery_svc.verify_otp_and_settle(
        delivery_id=delivery_id,
        submitted_otp=str(otp_code),
    )

    if not result.get("success"):
        status_code = 404 if "not found" in result.get("error", "").lower() else 400
        return jsonify(result), status_code

    return jsonify(result), 200


@api_bp.route("/deliveries/<delivery_id>/disburse-airtime", methods=["POST"])
def disburse_delivery_airtime(delivery_id):
    """Trigger or re-try airtime disbursement for a delivery."""
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    currency = data.get("currency")

    delivery_svc = get_delivery_service()
    result = delivery_svc.trigger_airtime_disbursement(
        delivery_id=delivery_id,
        amount=amount,
        currency=currency,
    )

    if not result.get("success"):
        return jsonify(result), 400

    return jsonify(result), 200


# --------------------------------------------------------------------------
# TELEPHONY UTILITY ENDPOINTS
# --------------------------------------------------------------------------

@api_bp.route("/telephony/send-sms", methods=["POST"])
def direct_send_sms():
    """Directly send an SMS via Africa's Talking API."""
    data = request.get_json() or {}
    to = data.get("to")
    message = data.get("message")
    sender_id = data.get("sender_id")

    if not to or not message:
        return jsonify(
            {"success": False, "error": "Missing required fields: 'to' and 'message'"}
        ), 400

    try:
        at_service = get_africastalking_service()
        result = at_service.send_sms(to=to, message=message, sender_id=sender_id)
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@api_bp.route("/telephony/send-airtime", methods=["POST"])
def direct_send_airtime():
    """Directly disburse airtime via Africa's Talking Airtime API."""
    data = request.get_json() or {}
    phone_number = data.get("phone_number")
    amount = data.get("amount")
    currency = data.get("currency", "KES")

    if not phone_number or amount is None:
        return jsonify(
            {
                "success": False,
                "error": "Missing required fields: 'phone_number' and 'amount'",
            }
        ), 400

    try:
        at_service = get_africastalking_service()
        result = at_service.send_airtime(
            phone_number=phone_number,
            amount=amount,
            currency_code=currency,
        )
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# --------------------------------------------------------------------------
# STATS & DASHBOARD METRICS
# --------------------------------------------------------------------------

@api_bp.route("/stats", methods=["GET"])
def delivery_stats():
    """Retrieve operational dashboard statistics."""
    total_deliveries = Delivery.query.count()
    completed_deliveries = Delivery.query.filter_by(status="COMPLETED").count()
    pending_deliveries = Delivery.query.filter_by(status="PENDING").count()
    otp_sent_deliveries = Delivery.query.filter_by(status="OTP_SENT").count()
    disbursed_count = Delivery.query.filter_by(airtime_status="DISBURSED").count()

    # Sum of all disbursed airtime payouts
    total_disbursed_amount = (
        db.session.query(db.func.sum(Delivery.payout_amount))
        .filter(Delivery.airtime_status.in_(["DISBURSED", "SIMULATED"]))
        .scalar()
        or 0.0
    )

    return jsonify(
        {
            "total_deliveries": total_deliveries,
            "completed": completed_deliveries,
            "pending": pending_deliveries,
            "otp_sent": otp_sent_deliveries,
            "airtime_disbursed_count": disbursed_count,
            "total_airtime_disbursed_kes": float(total_disbursed_amount),
        }
    ), 200

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models.agent import Agent
from app.models.delivery import Delivery

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/agents", methods=["POST"])
def create_agent():
    """Register a field agent with their home cell-tower zone."""
    data = request.get_json() or {}
    phone = data.get("phone_number")
    name = data.get("name")
    tower = data.get("registered_cell_tower_id")
    if not (phone and name and tower):
        return (
            jsonify({"error": "phone_number, name, registered_cell_tower_id are required"}),
            400,
        )
    if Agent.query.filter_by(phone_number=phone).first():
        return jsonify({"error": "agent already exists"}), 409
    agent = Agent(
        phone_number=phone,
        name=name,
        registered_cell_tower_id=tower,
        is_active=True,
    )
    db.session.add(agent)
    db.session.commit()
    return jsonify(agent.to_dict()), 201


@api_bp.route("/deliveries", methods=["POST"])
def create_delivery():
    """Create a delivery job bound to a destination cell-tower zone."""
    data = request.get_json() or {}
    required = ["delivery_code", "agent_id", "buyer_phone", "destination_cell_tower_id"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"missing required fields: {', '.join(missing)}"}), 400
    delivery = Delivery(
        delivery_code=data["delivery_code"],
        agent_id=data["agent_id"],
        buyer_phone=data["buyer_phone"],
        destination_cell_tower_id=data["destination_cell_tower_id"],
        zone_name=data.get("zone_name"),
        delivery_fee=int(data.get("delivery_fee", 50)),
    )
    db.session.add(delivery)
    db.session.commit()
    return jsonify(delivery.to_dict()), 201


@api_bp.route("/deliveries/<string:delivery_code>", methods=["GET"])
def get_delivery(delivery_code):
    delivery = Delivery.query.filter_by(delivery_code=delivery_code).first()
    if delivery is None:
        return jsonify({"error": "delivery not found"}), 404
    return jsonify(delivery.to_dict())


@api_bp.route("/deliveries", methods=["GET"])
def list_deliveries():
    return jsonify([d.to_dict() for d in Delivery.query.all()])

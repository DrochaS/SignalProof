import os

from flask import Flask, jsonify

from .extensions import cors, db, migrate
from .config import config_by_name
from .routes import register_blueprints

# Import models so they are registered with SQLAlchemy metadata before create_all().
from .models import Agent, Delivery, USSDSession  # noqa: F401


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")
    app = Flask(__name__)
    if isinstance(config_name, str):
        app.config.from_object(config_by_name[config_name])
    else:
        app.config.from_object(config_name)

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)

    # Wire up the AfricasTalking service with app config (credentials, mock/tower settings).
    from .services.africastalking import AfricasTalkingService

    mock_setting = str(app.config.get("MOCK_AT_SERVICES", "auto")).lower()
    at_service = AfricasTalkingService(
        username=app.config.get("AT_USERNAME"),
        api_key=app.config.get("AT_API_KEY"),
        sender_id=app.config.get("AT_SENDER_ID"),
        mock_mode=True if mock_setting in ("true", "1", "yes") else None,
        mock_network=app.config.get("MOCK_NETWORK", True),
        simulated_tower=app.config.get("SIMULATED_CELL_TOWER_ID", ""),
    )
    app.at_service = at_service
    app.extensions["signalproof_at_service"] = at_service

    register_blueprints(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "signalproof-ussd"}), 200

    with app.app_context():
        db.create_all()

    return app

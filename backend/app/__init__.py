import os

from flask import Flask, jsonify

from app.extensions import db, migrate
from app.config import config_by_name
from app.routes import register_blueprints
from app.services.africastalking import AfricasTalkingService

# Import models so they are registered with SQLAlchemy metadata before create_all().
from app.models import Agent, Delivery, USSDSession  # noqa: F401


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)

    # Wire up the AfricasTalking service with app config (credentials, mock mode, tower).
    at_service = AfricasTalkingService()
    at_service.init_app(app)
    app.at_service = at_service

    register_blueprints(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "signalproof-ussd"}), 200

    with app.app_context():
        db.create_all()

    return app

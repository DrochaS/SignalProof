"""SignalProof Flask Application Factory."""

import logging
from flask import Flask
from backend.app.config import Config
from backend.app.extensions import cors, db


def create_app(config_class=Config):
    """Application factory for SignalProof backend."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    cors.init_app(app)

    # Register blueprints
    from backend.app.routes.api_routes import api_bp
    from backend.app.routes.ussd_routes import ussd_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(ussd_bp)

    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    # Ensure tables exist
    with app.app_context():
        import backend.app.models  # noqa: F401
        db.create_all()

    return app

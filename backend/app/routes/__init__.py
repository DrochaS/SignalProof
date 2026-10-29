from .api_routes import api_bp
from .ussd_routes import ussd_bp


def register_blueprints(app):
    app.register_blueprint(ussd_bp)
    app.register_blueprint(api_bp)


__all__ = ["api_bp", "register_blueprints", "ussd_bp"]

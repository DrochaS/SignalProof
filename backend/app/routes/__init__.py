from app.routes.ussd_routes import ussd_bp
from app.routes.api_routes import api_bp


def register_blueprints(app):
    app.register_blueprint(ussd_bp)
    app.register_blueprint(api_bp)

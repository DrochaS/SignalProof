import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(key, default):
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return int(default)


class Config:
    """Base configuration for SignalProof backend."""

    SECRET_KEY = os.getenv("SECRET_KEY", "signalproof-dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///signalproof.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # AfricasTalking credentials
    AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
    AT_API_KEY = os.getenv("AT_API_KEY", "")
    AT_BASE_URL = os.getenv("AT_BASE_URL", "https://api.africastalking.com").rstrip("/")

    # USSD
    USSD_CODE = os.getenv("USSD_CODE", "*384*#")

    # OTP / delivery / payout
    OTP_LENGTH = _env_int("OTP_LENGTH", "4")
    DELIVERY_FEE_DEFAULT = _env_int("DELIVERY_FEE_DEFAULT", "50")  # KES
    CURRENCY_CODE = os.getenv("CURRENCY_CODE", "KES")

    # Network telemetry (cell-tower) simulation
    MOCK_NETWORK = os.getenv("MOCK_NETWORK", "true").lower() == "true"
    SIMULATED_CELL_TOWER_ID = os.getenv("SIMULATED_CELL_TOWER_ID", "")

    # USSD session TTL
    SESSION_TTL_MINUTES = _env_int("SESSION_TTL_MINUTES", "10")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

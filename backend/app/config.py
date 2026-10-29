import os
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "signalproof-hackathon-secret-key-2026")
    database_url = os.getenv(
        "DATABASE_URL", f"sqlite:///{backend_dir / 'signalproof.db'}"
    )
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Africa's Talking Telephony Configuration
    AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
    AT_API_KEY = os.getenv("AT_API_KEY", "")
    AT_SENDER_ID = os.getenv("AT_SENDER_ID", None)
    AT_ENVIRONMENT = os.getenv("AT_ENVIRONMENT", "sandbox")

    # Default Airtime & Currency Settings
    DEFAULT_AIRTIME_AMOUNT = float(os.getenv("DEFAULT_AIRTIME_AMOUNT", "50.0"))
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "KES")

    # USSD and network telemetry
    USSD_CODE = os.getenv("USSD_CODE", "*384*#")
    DELIVERY_FEE_DEFAULT = int(os.getenv("DELIVERY_FEE_DEFAULT", "50"))
    CURRENCY_CODE = os.getenv("CURRENCY_CODE", DEFAULT_CURRENCY)
    OTP_LENGTH = int(os.getenv("OTP_LENGTH", "4"))
    MOCK_NETWORK = os.getenv("MOCK_NETWORK", "true").lower() in ("true", "1", "yes")
    SIMULATED_CELL_TOWER_ID = os.getenv("SIMULATED_CELL_TOWER_ID", "")
    SESSION_TTL_MINUTES = int(os.getenv("SESSION_TTL_MINUTES", "10"))

    # Mock Mode: 'true' / '1' forces simulation, 'false' forces real API,
    # 'auto' automatically uses simulation when API key is missing or dummy
    MOCK_AT_SERVICES = os.getenv("MOCK_AT_SERVICES", "auto").lower()


class TestConfig(Config):
    """Test configuration using in-memory database."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MOCK_AT_SERVICES = "true"


TestingConfig = TestConfig


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestConfig,
    "production": ProductionConfig,
}

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
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{backend_dir / 'signalproof.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Africa's Talking Telephony Configuration
    AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
    AT_API_KEY = os.getenv("AT_API_KEY", "")
    AT_SENDER_ID = os.getenv("AT_SENDER_ID", None)
    AT_ENVIRONMENT = os.getenv("AT_ENVIRONMENT", "sandbox")

    # Default Airtime & Currency Settings
    DEFAULT_AIRTIME_AMOUNT = float(os.getenv("DEFAULT_AIRTIME_AMOUNT", "50.0"))
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "KES")

    # Mock Mode: 'true' / '1' forces simulation, 'false' forces real API,
    # 'auto' automatically uses simulation when API key is missing or dummy
    MOCK_AT_SERVICES = os.getenv("MOCK_AT_SERVICES", "auto").lower()


class TestConfig(Config):
    """Test configuration using in-memory database."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MOCK_AT_SERVICES = "true"

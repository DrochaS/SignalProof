import hashlib
import logging

import requests

logger = logging.getLogger(__name__)


class ATServiceError(Exception):
    """Raised when an AfricasTalking upstream call fails."""


class AfricasTalkingService:
    """Thin client over AfricasTalking: Network Insights, SMS, Airtime.

    Runs in simulated mode when MOCK_NETWORK=true or no AT_API_KEY is configured,
    so the USSD flow can be developed and demoed without live telco credentials.
    """

    def __init__(self, app=None):
        self.app = app
        self.username = "sandbox"
        self.api_key = ""
        self.base_url = "https://api.africastalking.com"
        self.mock_network = True
        self.simulated_tower = ""
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.username = app.config["AT_USERNAME"]
        self.api_key = app.config["AT_API_KEY"]
        self.base_url = app.config["AT_BASE_URL"].rstrip("/")
        self.mock_network = app.config["MOCK_NETWORK"]
        self.simulated_tower = app.config["SIMULATED_CELL_TOWER_ID"]

    def _headers(self):
        return {
            "Accept": "application/json",
            "apiKey": self.api_key,
        }

    # ---- Network telemetry (cell tower) ----
    def get_cell_tower(self, phone_number):
        """Return the observed cell-tower id for the subscriber's active SIM.

        Returns a dict: {"phone_number", "cell_tower_id", "source"}.
        """
        if self.mock_network or not self.api_key:
            tower = self.simulated_tower or self._deterministic_tower(phone_number)
            logger.info("SIMULATED network tower for %s: %s", phone_number, tower)
            return {
                "phone_number": phone_number,
                "cell_tower_id": tower,
                "source": "simulated",
            }

        url = f"{self.base_url}/network-insights"
        try:
            resp = requests.get(
                url, params={"phoneNumber": phone_number}, headers=self._headers(), timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "phone_number": phone_number,
                "cell_tower_id": data.get("cellTowerId") or data.get("cell_tower_id"),
                "source": "africas_talking",
            }
        except requests.RequestException as exc:
            logger.exception("AT network insights failed for %s", phone_number)
            raise ATServiceError(f"network insights unavailable: {exc}")

    @staticmethod
    def _deterministic_tower(phone_number):
        digest = hashlib.sha256(phone_number.encode()).hexdigest()
        lac = int(digest[:4], 16) % 65535
        cell = int(digest[4:8], 16) % 65535
        return f"639-01-{lac}-{cell}"

    # ---- SMS ----
    def send_sms(self, to, message):
        if self.mock_network or not self.api_key:
            logger.info("SIMULATED SMS to %s: %s", to, message)
            return {
                "status": "simulated",
                "recipients": [{"number": to, "status": "sent", "message": message}],
            }

        url = f"{self.base_url}/messaging/v1/messaging"
        data = {
            "username": self.username,
            "to": to,
            "message": message,
            "from": "SIGNAL",
        }
        try:
            resp = requests.post(url, data=data, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.exception("AT SMS failed to %s", to)
            raise ATServiceError(f"sms delivery failed: {exc}")

    # ---- Airtime / mobile-money disbursement ----
    def disburse_airtime(self, phone_number, amount, currency_code="KES"):
        if self.mock_network or not self.api_key:
            logger.info(
                "SIMULATED airtime %s %s to %s", amount, currency_code, phone_number
            )
            return {
                "status": "simulated",
                "recipients": [
                    {
                        "number": phone_number,
                        "amount": amount,
                        "currency_code": currency_code,
                        "status": "sent",
                    }
                ],
            }

        url = f"{self.base_url}/airtime/v1/send"
        data = {
            "username": self.username,
            "recipients": [
                {
                    "phoneNumber": phone_number,
                    "amount": amount,
                    "currencyCode": currency_code,
                }
            ],
        }
        try:
            resp = requests.post(url, json=data, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.exception("AT airtime disbursement failed to %s", phone_number)
            raise ATServiceError(f"airtime disbursement failed: {exc}")

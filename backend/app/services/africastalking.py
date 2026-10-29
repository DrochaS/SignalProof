"""Africa's Talking SDK Wrapper for SignalProof.

Provides telephony integration for:
- SMS OTP dispatch to buyers upon verified agent arrival
- Dual delivery confirmation SMS receipts (buyer escrow release & agent payout notice)
- Automated Airtime disbursement triggers to agent SIM cards upon verified fulfillment
- Robust phone number normalization (+254 Kenya E.164)
- Graceful mock/simulation fallback when running tests or in environments without live AT credentials
"""

import json
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import africastalking
import requests
from flask import current_app, has_app_context

logger = logging.getLogger("signalproof.telephony")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [SignalProof-Telephony] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def normalize_phone_number(phone: str, default_country_code: str = "+254") -> str:
    """Normalize phone number to Africa's Talking compatible E.164 format.

    Examples:
        '0712345678'   -> '+254712345678'
        '0112345678'   -> '+254112345678'
        '254712345678' -> '+254712345678'
        '+254712345678'-> '+254712345678'
    """
    if not phone:
        raise ValueError("Phone number cannot be empty")

    cleaned = re.sub(r"[\s\-\(\)]", "", str(phone).strip())

    # Format 07XX or 01XX (Kenya 10 digits)
    if re.match(r"^0[17]\d{8}$", cleaned):
        return default_country_code + cleaned[1:]

    # Format 254XXXXXXXXX (12 digits)
    if re.match(r"^254\d{9}$", cleaned):
        return f"+{cleaned}"

    # Already has '+' prefix and reasonable length
    if cleaned.startswith("+") and len(cleaned) >= 10:
        return cleaned

    # Fallback if digits only
    if cleaned.isdigit():
        return f"+{cleaned}"

    return cleaned


class AfricasTalkingService:
    """Production and Sandbox wrapper for Africa's Talking Telephony & Financial APIs."""

    def __init__(
        self,
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        sender_id: Optional[str] = None,
        mock_mode: Optional[bool] = None,
        mock_network: Optional[bool] = None,
        simulated_tower: str = "",
    ):
        self.username = username or os.getenv("AT_USERNAME", "sandbox")
        self.api_key = api_key or os.getenv("AT_API_KEY", "")
        self.sender_id = sender_id or os.getenv("AT_SENDER_ID", None)

        env_mock = os.getenv("MOCK_AT_SERVICES", "auto").lower()

        # Decide if running in mock/simulation mode
        if mock_mode is not None:
            self.is_mock = mock_mode
        elif env_mock in ("true", "1", "yes"):
            self.is_mock = True
        elif not self.api_key or self.api_key in (
            "your_africastalking_api_key_here",
            "test",
            "mock",
            "placeholder",
        ):
            self.is_mock = True
        else:
            self.is_mock = False

        self.sent_sms_log: List[Dict[str, Any]] = []
        self.sent_airtime_log: List[Dict[str, Any]] = []
        self.mock_network = (
            os.getenv("MOCK_NETWORK", "true").lower() in ("true", "1", "yes")
            if mock_network is None
            else mock_network
        )
        self.simulated_tower = simulated_tower or os.getenv(
            "SIMULATED_CELL_TOWER_ID", ""
        )

        self._sms_service = None
        self._airtime_service = None
        self._app_service = None

        if not self.is_mock:
            try:
                africastalking.initialize(self.username, self.api_key)
                self._sms_service = africastalking.SMS
                self._airtime_service = africastalking.Airtime
                self._app_service = africastalking.Application
                logger.info(
                    "Africa's Talking SDK successfully initialized for user: %s",
                    self.username,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Africa's Talking SDK (%s). Falling back to simulated telephony mode.",
                    str(e),
                )
                self.is_mock = True
        else:
            logger.info(
                "SignalProof Africa's Talking service initialized in SIMULATION/SANDBOX mode (no external HTTP calls)."
            )

    def get_cell_tower(self, phone_number: str) -> Dict[str, Any]:
        """Return the subscriber's observed cell tower or a deterministic mock."""
        normalized_phone = normalize_phone_number(phone_number)
        if self.mock_network or self.is_mock:
            tower = self.simulated_tower or self._deterministic_tower(normalized_phone)
            return {
                "phone_number": normalized_phone,
                "cell_tower_id": tower,
                "source": "simulated",
            }

        base_url = os.getenv(
            "AT_BASE_URL", "https://api.africastalking.com"
        ).rstrip("/")
        try:
            response = requests.get(
                f"{base_url}/network-insights",
                params={"phoneNumber": normalized_phone},
                headers={"apiKey": self.api_key, "Accept": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.exception("Africa's Talking network insights failed")
            raise RuntimeError("Network insights unavailable") from exc

        return {
            "phone_number": normalized_phone,
            "cell_tower_id": payload.get("cellTowerId")
            or payload.get("cell_tower_id"),
            "source": "africas_talking",
        }

    @staticmethod
    def _deterministic_tower(phone_number: str) -> str:
        digest = hashlib.sha256(phone_number.encode()).hexdigest()
        lac = int(digest[:4], 16) % 65535
        cell = int(digest[4:8], 16) % 65535
        return f"639-01-{lac}-{cell}"

    # --------------------------------------------------------------------------
    # CORE SMS APIS
    # --------------------------------------------------------------------------

    def send_sms(
        self,
        to: Union[str, List[str]],
        message: str,
        sender_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an SMS via Africa's Talking SMS API.

        :param to: Single phone number string or list of recipient phone numbers
        :param message: Text body of the SMS
        :param sender_id: Optional alphanumeric sender ID or shortcode
        :return: Standardized result dictionary
        """
        recipients = [to] if isinstance(to, str) else list(to)
        normalized_recipients = [normalize_phone_number(p) for p in recipients]
        active_sender_id = sender_id or self.sender_id

        logger.info(
            "Sending SMS to %s | body: '%s' | sender_id: %s",
            normalized_recipients,
            message,
            active_sender_id,
        )

        if self.is_mock:
            # Simulated Africa's Talking response structure
            mock_recipients = []
            message_ids = []
            for phone in normalized_recipients:
                msg_id = f"ATXid_sim_{uuid.uuid4().hex[:12]}"
                message_ids.append(msg_id)
                mock_recipients.append(
                    {
                        "cost": "KES 0.8000",
                        "messageId": msg_id,
                        "number": phone,
                        "status": "Success",
                        "statusCode": 101,
                    }
                )

            mock_response = {
                "SMSMessageData": {
                    "Message": f"Sent to {len(normalized_recipients)}/{len(normalized_recipients)} Total Cost: KES {0.8 * len(normalized_recipients):.4f}",
                    "Recipients": mock_recipients,
                }
            }

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recipients": normalized_recipients,
                "message": message,
                "sender_id": active_sender_id,
                "response": mock_response,
                "simulated": True,
            }
            self.sent_sms_log.append(log_entry)

            return {
                "success": True,
                "message": message,
                "recipients": normalized_recipients,
                "message_ids": message_ids,
                "raw_response": mock_response,
                "simulated": True,
            }

        # Real Africa's Talking API call
        try:
            kwargs = {}
            if active_sender_id:
                kwargs["sender_id"] = active_sender_id

            response = self._sms_service.send(
                message=message,
                recipients=normalized_recipients,
                **kwargs,
            )

            recipients_data = (
                response.get("SMSMessageData", {}).get("Recipients", [])
                if isinstance(response, dict)
                else []
            )
            message_ids = [
                r.get("messageId") for r in recipients_data if "messageId" in r
            ]

            return {
                "success": True,
                "message": message,
                "recipients": normalized_recipients,
                "message_ids": message_ids,
                "raw_response": response,
                "simulated": False,
            }
        except Exception as e:
            logger.error("Africa's Talking SMS send error: %s", str(e))
            return {
                "success": False,
                "error": str(e),
                "recipients": normalized_recipients,
                "message": message,
                "simulated": False,
            }

    # --------------------------------------------------------------------------
    # CORE AIRTIME APIS
    # --------------------------------------------------------------------------

    def send_airtime(
        self,
        phone_number: str,
        amount: Union[float, int, str],
        currency_code: str = "KES",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Disburse Airtime to a recipient phone number via Africa's Talking.

        :param phone_number: Recipient agent/rider phone number (e.g. +254722000111)
        :param amount: Airtime amount in currency_code (e.g. 50.0)
        :param currency_code: Currency code (e.g. 'KES', 'UGX', 'TZS', 'NGN')
        :param idempotency_key: Optional idempotency header for payment safety
        :return: Standardized result dictionary
        """
        normalized_phone = normalize_phone_number(phone_number)
        num_amount = float(amount)
        if num_amount <= 0:
            raise ValueError(f"Airtime amount must be greater than zero, got {amount}")

        logger.info(
            "Disbursing airtime payout of %s %.2f to %s",
            currency_code,
            num_amount,
            normalized_phone,
        )

        if self.is_mock:
            request_id = f"ATQid_sim_{uuid.uuid4().hex[:12]}"
            mock_response = {
                "errorMessage": "None",
                "numSent": 1,
                "totalAmount": f"{currency_code} {num_amount:.2f}",
                "totalDiscount": f"{currency_code} 0.00",
                "responses": [
                    {
                        "phoneNumber": normalized_phone,
                        "errorMessage": "None",
                        "amount": f"{currency_code} {num_amount:.2f}",
                        "status": "Sent",
                        "requestId": request_id,
                        "discount": f"{currency_code} 0.00",
                    }
                ],
            }

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phone_number": normalized_phone,
                "amount": num_amount,
                "currency": currency_code,
                "transaction_id": request_id,
                "response": mock_response,
                "simulated": True,
            }
            self.sent_airtime_log.append(log_entry)

            return {
                "success": True,
                "phone_number": normalized_phone,
                "amount": num_amount,
                "currency": currency_code,
                "transaction_id": request_id,
                "status": "Sent",
                "raw_response": mock_response,
                "simulated": True,
            }

        # Real Africa's Talking API call
        try:
            # AT Python SDK accepts phone_number, amount (str), currency_code (str)
            response = self._airtime_service.send(
                phone_number=normalized_phone,
                amount=str(num_amount),
                currency_code=currency_code,
                idempotency_key=idempotency_key,
            )

            responses_list = (
                response.get("responses", []) if isinstance(response, dict) else []
            )
            first_resp = responses_list[0] if responses_list else {}
            request_id = first_resp.get("requestId")
            resp_status = first_resp.get("status", "Sent")
            error_msg = (
                response.get("errorMessage")
                if response.get("errorMessage") != "None"
                else None
            )

            is_success = resp_status in ("Sent", "Queued", "Success") and not error_msg

            return {
                "success": is_success,
                "phone_number": normalized_phone,
                "amount": num_amount,
                "currency": currency_code,
                "transaction_id": request_id,
                "status": resp_status,
                "raw_response": response,
                "simulated": False,
                "error": error_msg,
            }
        except Exception as e:
            logger.error("Africa's Talking Airtime send error: %s", str(e))
            return {
                "success": False,
                "phone_number": normalized_phone,
                "amount": num_amount,
                "currency": currency_code,
                "error": str(e),
                "simulated": False,
            }

    # --------------------------------------------------------------------------
    # HIGH-LEVEL SIGNALPROOF WORKFLOW HELPERS
    # --------------------------------------------------------------------------

    def send_otp_sms(
        self,
        buyer_phone: str,
        otp_code: str,
        delivery_id: Optional[Union[str, int]] = None,
        zone_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Trigger Automated Buyer OTP Dispatch once agent location is verified.

        Exact template per SignalProof specification:
        "SignalProof: Agent is on site. Your delivery verification code is 4821."
        """
        message = (
            f"SignalProof: Agent is on site. Your delivery verification code is {otp_code}."
        )
        result = self.send_sms(to=buyer_phone, message=message)
        result["delivery_id"] = delivery_id
        result["otp_code"] = otp_code
        result["event"] = "BUYER_OTP_DISPATCHED"
        return result

    def send_delivery_receipt_sms(
        self,
        buyer_phone: str,
        agent_phone: str,
        delivery_id: Union[str, int],
        airtime_amount: float = 50.0,
        currency: str = "KES",
    ) -> Dict[str, Any]:
        """Dispatch dual SMS receipts upon verified settlement & escrow release.

        Buyer message:
        "SignalProof: Delivery #{delivery_id} completed successfully. Escrow funds released. Thank you!"

        Agent message:
        "SignalProof: Delivery #{delivery_id} confirmed! {currency} {airtime_amount:.0f} airtime payout has been credited to your number."
        """
        buyer_msg = (
            f"SignalProof: Delivery #{delivery_id} completed successfully. "
            f"Escrow funds released. Thank you!"
        )
        agent_msg = (
            f"SignalProof: Delivery #{delivery_id} confirmed! "
            f"{currency} {airtime_amount:.0f} airtime payout has been credited to your number."
        )

        buyer_receipt = self.send_sms(to=buyer_phone, message=buyer_msg)
        agent_receipt = self.send_sms(to=agent_phone, message=agent_msg)

        return {
            "success": buyer_receipt.get("success", False)
            and agent_receipt.get("success", False),
            "buyer_receipt": buyer_receipt,
            "agent_receipt": agent_receipt,
            "delivery_id": delivery_id,
            "event": "DELIVERY_RECEIPTS_DISPATCHED",
        }

    def disburse_agent_payout(
        self,
        agent_phone: str,
        amount: float = 50.0,
        currency: str = "KES",
        delivery_id: Optional[Union[str, int]] = None,
    ) -> Dict[str, Any]:
        """Instant Escrow Settlement: Disburses delivery fee reward directly to agent SIM."""
        idempotency_key = (
            f"sp_payout_{delivery_id}_{int(datetime.now(timezone.utc).timestamp())}"
            if delivery_id
            else None
        )
        result = self.send_airtime(
            phone_number=agent_phone,
            amount=amount,
            currency_code=currency,
            idempotency_key=idempotency_key,
        )
        result["delivery_id"] = delivery_id
        result["event"] = "AGENT_AIRTIME_PAYOUT"
        return result

    def get_account_status(self) -> Dict[str, Any]:
        """Fetch current Africa's Talking account balance & environment status."""
        if self.is_mock:
            return {
                "status": "SIMULATION_MODE",
                "username": self.username,
                "balance": "KES 10000.00 (Simulated)",
                "simulated": True,
            }
        try:
            data = self._app_service.fetch_application_data()
            user_data = data.get("UserData", {})
            return {
                "status": "LIVE",
                "username": self.username,
                "balance": user_data.get("balance", "Unknown"),
                "simulated": False,
                "raw": data,
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "username": self.username,
                "error": str(e),
                "simulated": False,
            }

    def clear_logs(self) -> None:
        """Utility for test suites to reset simulated dispatch logs."""
        self.sent_sms_log.clear()
        self.sent_airtime_log.clear()


# Module-level singleton instance
_at_service_instance: Optional[AfricasTalkingService] = None


def get_africastalking_service(force_new: bool = False) -> AfricasTalkingService:
    """Retrieve or create the Africa's Talking service instance."""
    global _at_service_instance
    if not force_new and has_app_context():
        app_service = current_app.extensions.get("signalproof_at_service")
        if app_service is not None:
            return app_service
    if _at_service_instance is None or force_new:
        _at_service_instance = AfricasTalkingService()
    return _at_service_instance


# Standalone function exports matching user prompt scope
def send_otp_sms(
    buyer_phone: str,
    otp_code: str,
    delivery_id: Optional[Union[str, int]] = None,
    zone_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper: Send delivery verification OTP to buyer."""
    return get_africastalking_service().send_otp_sms(
        buyer_phone=buyer_phone,
        otp_code=otp_code,
        delivery_id=delivery_id,
        zone_name=zone_name,
    )


def send_delivery_receipt_sms(
    buyer_phone: str,
    agent_phone: str,
    delivery_id: Union[str, int],
    airtime_amount: float = 50.0,
    currency: str = "KES",
) -> Dict[str, Any]:
    """Helper: Send dual completion & payout receipts."""
    return get_africastalking_service().send_delivery_receipt_sms(
        buyer_phone=buyer_phone,
        agent_phone=agent_phone,
        delivery_id=delivery_id,
        airtime_amount=airtime_amount,
        currency=currency,
    )


def disburse_airtime(
    agent_phone: str,
    amount: float = 50.0,
    currency: str = "KES",
    delivery_id: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """Helper: Disburse airtime bonus to agent."""
    return get_africastalking_service().disburse_agent_payout(
        agent_phone=agent_phone,
        amount=amount,
        currency=currency,
        delivery_id=delivery_id,
    )

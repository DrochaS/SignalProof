"""Unit and Integration Tests for SignalProof Africa's Talking Telephony and Deliveries API."""

import pytest
from backend.app import create_app
from backend.app.config import TestConfig
from backend.app.extensions import db
from backend.app.models.delivery import Delivery
from backend.app.services.africastalking import (
    AfricasTalkingService,
    get_africastalking_service,
    normalize_phone_number,
    send_otp_sms,
    send_delivery_receipt_sms,
    disburse_airtime,
)
from backend.app.services.delivery_service import DeliveryService


@pytest.fixture
def app():
    """Create application configured for testing."""
    test_app = create_app(TestConfig)
    # Ensure Africa's Talking service uses mock mode during test runs
    import backend.app.services.africastalking as at_mod
    at_mod._at_service_instance = AfricasTalkingService(
        username="sandbox",
        api_key="mock_test_key",
        mock_mode=True,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client fixture."""
    return app.test_client()


@pytest.fixture
def at_service():
    """Test Africa's Talking service instance in mock mode."""
    service = AfricasTalkingService(
        username="sandbox",
        api_key="mock_key",
        mock_mode=True,
    )
    service.clear_logs()
    return service


# ==============================================================================
# 1. PHONE NUMBER NORMALIZATION TESTS
# ==============================================================================

def test_normalize_phone_number():
    # Kenya 07XX format
    assert normalize_phone_number("0712345678") == "+254712345678"
    # Kenya 01XX format
    assert normalize_phone_number("0112345678") == "+254112345678"
    # Kenya 254XXXXXXXXX format without plus
    assert normalize_phone_number("254722000111") == "+254722000111"
    # Already E.164
    assert normalize_phone_number("+254722000111") == "+254722000111"
    # Number with spaces and dashes
    assert normalize_phone_number("0712-345 678") == "+254712345678"

    with pytest.raises(ValueError):
        normalize_phone_number("")


# ==============================================================================
# 2. AFRICA'S TALKING TELEPHONY WRAPPER TESTS
# ==============================================================================

def test_at_send_sms_simulation(at_service):
    result = at_service.send_sms(
        to="0712345678",
        message="SignalProof: Test message",
    )
    assert result["success"] is True
    assert result["simulated"] is True
    assert "+254712345678" in result["recipients"]
    assert len(result["message_ids"]) == 1
    assert len(at_service.sent_sms_log) == 1


def test_at_send_airtime_simulation(at_service):
    result = at_service.send_airtime(
        phone_number="0722000111",
        amount=50.0,
        currency_code="KES",
    )
    assert result["success"] is True
    assert result["simulated"] is True
    assert result["amount"] == 50.0
    assert result["currency"] == "KES"
    assert result["phone_number"] == "+254722000111"
    assert result["transaction_id"].startswith("ATQid_sim_")
    assert len(at_service.sent_airtime_log) == 1


def test_at_send_otp_sms(at_service):
    result = at_service.send_otp_sms(
        buyer_phone="0712345678",
        otp_code="4821",
        delivery_id=101,
        zone_name="Westlands Zone",
    )
    assert result["success"] is True
    expected_msg = "SignalProof: Agent is on site. Your delivery verification code is 4821."
    assert result["message"] == expected_msg
    assert result["otp_code"] == "4821"
    assert result["delivery_id"] == 101


def test_at_send_delivery_receipt_sms(at_service):
    result = at_service.send_delivery_receipt_sms(
        buyer_phone="0712345678",
        agent_phone="0722000111",
        delivery_id=101,
        airtime_amount=50.0,
        currency="KES",
    )
    assert result["success"] is True
    assert "buyer_receipt" in result
    assert "agent_receipt" in result

    # Check buyer confirmation
    buyer_msg = result["buyer_receipt"]["message"]
    assert "Delivery #101 completed successfully" in buyer_msg
    assert "Escrow funds released" in buyer_msg

    # Check agent payout notification
    agent_msg = result["agent_receipt"]["message"]
    assert "Delivery #101 confirmed" in agent_msg
    assert "KES 50 airtime payout has been credited" in agent_msg


# ==============================================================================
# 3. DELIVERY SERVICE & LIFECYCLE TESTS
# ==============================================================================

def test_delivery_lifecycle_with_telephony(app, at_service):
    delivery_svc = DeliveryService(at_service=at_service)

    # 1. Create delivery
    delivery = delivery_svc.create_delivery(
        buyer_name="Alice Wanjiku",
        buyer_phone="0712345678",
        agent_id="AG-001",
        agent_name="Brian Kipkorir",
        agent_phone="0722000111",
        destination_zone="Westlands Zone",
        destination_tower_id="TOW-NBO-042",
        payout_amount=50.0,
        currency="KES",
        custom_otp="4821",
    )

    assert delivery.id is not None
    assert delivery.otp_code == "4821"
    assert delivery.status == "PENDING"
    assert delivery.airtime_status == "NOT_DISBURSED"

    # 2. Trigger Arrival Handshake & OTP SMS Dispatch to Buyer
    otp_dispatch = delivery_svc.trigger_otp_dispatch(
        delivery_id=delivery.id,
        cell_tower_id="TOW-NBO-042",
    )
    assert otp_dispatch["success"] is True
    assert delivery.status == "OTP_SENT"
    assert len(at_service.sent_sms_log) == 1
    assert "4821" in at_service.sent_sms_log[0]["message"]

    # 3. Attempt invalid OTP
    fail_result = delivery_svc.verify_otp_and_settle(
        delivery_id=delivery.id,
        submitted_otp="9999",
    )
    assert fail_result["success"] is False
    assert fail_result["error"] == "Invalid OTP code"
    assert delivery.status == "OTP_SENT"
    assert delivery.otp_attempts == 1

    # 4. Submit correct OTP: verifies and settles instantly
    settle_result = delivery_svc.verify_otp_and_settle(
        delivery_id=delivery.id,
        submitted_otp="4821",
    )
    assert settle_result["success"] is True
    assert delivery.status == "COMPLETED"
    assert delivery.airtime_status == "DISBURSED"
    assert delivery.airtime_transaction_id is not None

    # Check that airtime payout was disbursed
    assert len(at_service.sent_airtime_log) == 1
    airtime_entry = at_service.sent_airtime_log[0]
    assert airtime_entry["amount"] == 50.0
    assert airtime_entry["phone_number"] == "+254722000111"

    # Check dual SMS receipts sent
    # Total SMS sent: 1 OTP SMS + 1 Buyer Receipt + 1 Agent Receipt = 3 SMS
    assert len(at_service.sent_sms_log) == 3


# ==============================================================================
# 4. REST API ENDPOINTS TESTS (/api/deliveries)
# ==============================================================================

def test_api_deliveries_crud(client):
    # Create delivery
    payload = {
        "buyer_name": "Grace Muthoni",
        "buyer_phone": "0798765432",
        "agent_id": "AG-002",
        "agent_name": "David Ochieng",
        "agent_phone": "0711223344",
        "package_description": "Electronics Package",
        "destination_zone": "Kilimani Zone",
        "destination_tower_id": "TOW-NBO-019",
        "payout_amount": 75.0,
        "currency": "KES",
        "otp_code": "7319",
    }
    resp = client.post("/api/deliveries", json=payload)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    delivery_id = data["delivery"]["id"]
    assert data["delivery"]["otp_code"] == "7319"
    assert data["delivery"]["payout_amount"] == 75.0

    # Get single delivery
    get_resp = client.get(f"/api/deliveries/{delivery_id}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["delivery"]["buyer_name"] == "Grace Muthoni"

    # List deliveries
    list_resp = client.get("/api/deliveries")
    assert list_resp.status_code == 200
    list_data = list_resp.get_json()
    assert list_data["total"] >= 1


def test_api_deliveries_send_otp_and_verify(client):
    # Create delivery
    create_resp = client.post(
        "/api/deliveries",
        json={
            "buyer_name": "Peter Kamau",
            "buyer_phone": "+254712000000",
            "agent_id": "AG-003",
            "agent_phone": "+254722999999",
            "otp_code": "6543",
            "destination_tower_id": "TOW-MSA-001",
        },
    )
    delivery_id = create_resp.get_json()["delivery"]["id"]

    # Send OTP
    send_otp_resp = client.post(
        f"/api/deliveries/{delivery_id}/send-otp",
        json={"cell_tower_id": "TOW-MSA-001"},
    )
    assert send_otp_resp.status_code == 200
    assert send_otp_resp.get_json()["success"] is True

    # Verify wrong OTP
    wrong_otp_resp = client.post(
        f"/api/deliveries/{delivery_id}/verify-otp",
        json={"otp_code": "0000"},
    )
    assert wrong_otp_resp.status_code == 400
    assert "Invalid OTP" in wrong_otp_resp.get_json()["error"]

    # Verify correct OTP
    correct_otp_resp = client.post(
        f"/api/deliveries/{delivery_id}/verify-otp",
        json={"otp_code": "6543"},
    )
    assert correct_otp_resp.status_code == 200
    verify_data = correct_otp_resp.get_json()
    assert verify_data["success"] is True
    assert verify_data["delivery"]["status"] == "COMPLETED"
    assert verify_data["delivery"]["airtime_status"] == "DISBURSED"


def test_api_telephony_endpoints(client):
    # Test SMS endpoint
    sms_resp = client.post(
        "/api/telephony/send-sms",
        json={"to": "0712345678", "message": "SignalProof system broadcast"},
    )
    assert sms_resp.status_code == 200
    assert sms_resp.get_json()["success"] is True

    # Test Airtime endpoint
    airtime_resp = client.post(
        "/api/telephony/send-airtime",
        json={"phone_number": "0722111222", "amount": 20.0, "currency": "KES"},
    )
    assert airtime_resp.status_code == 200
    assert airtime_resp.get_json()["success"] is True

    # Test status endpoint
    status_resp = client.get("/api/telephony/status")
    assert status_resp.status_code == 200

    # Test stats endpoint
    stats_resp = client.get("/api/stats")
    assert stats_resp.status_code == 200
    assert "total_deliveries" in stats_resp.get_json()

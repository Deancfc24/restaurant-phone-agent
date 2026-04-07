"""End-to-end tests for the Restaurant Phone Agent.

Runs against the live FastAPI app (in-process via TestClient).

Usage:
    python -m pytest tests/test_agent.py -v
    ONTOPO_LIVE_TESTS=1 python -m pytest tests/test_agent.py -v -k ontopo_live
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from src.database import Base, Restaurant, SessionLocal, engine, init_db
from src.main import app

client = TestClient(app)


@pytest.fixture(autouse=True, scope="session")
def _setup_db():
    """Initialise the test database."""
    init_db()
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_restaurant() -> str:
    """Insert a test restaurant and return its ID."""
    with SessionLocal() as db:
        r = Restaurant(
            name="Test Restaurant",
            venue_id="test-venue",
            city="tel-aviv",
            reservation_system="tabit",
            vapi_assistant_id="test-assistant-id",
            is_active=True,
        )
        db.add(r)
        db.commit()
        return r.id


def _webhook_call(
    tool_name: str, arguments: dict, assistant_id: str = "test-assistant-id"
) -> dict:
    """Simulate a Vapi tool-call webhook and return parsed results."""
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {"assistantId": assistant_id},
            "toolWithToolCallList": [
                {
                    "toolCall": {
                        "id": f"test-{tool_name}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": arguments,
                        },
                    }
                }
            ],
        }
    }
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["name"] == tool_name
    assert result["toolCallId"] == f"test-{tool_name}"
    return json.loads(result["result"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_restaurant_list_page(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Mia Dashboard" in resp.text

    def test_new_restaurant_form(self):
        resp = client.get("/restaurants/new")
        assert resp.status_code == 200
        assert "Add New Restaurant" in resp.text

    def test_create_restaurant_via_form(self):
        resp = client.post(
            "/api/restaurants",
            data={
                "name": "Dashboard Test",
                "reservation_system": "ontopo",
                "venue_id": "dash-test",
                "city": "tel-aviv",
                "phone_number": "",
                "vapi_phone_number_id": "",
                "tabit_organization_id": "",
                "tabit_api_key": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_restaurant_detail_page(self):
        rid = _create_test_restaurant()
        resp = client.get(f"/restaurants/{rid}")
        assert resp.status_code == 200
        assert "Test Restaurant" in resp.text


# ---------------------------------------------------------------------------
# Webhook routing
# ---------------------------------------------------------------------------

class TestWebhookRouting:
    @pytest.fixture(autouse=True)
    def _ensure_restaurant(self):
        _create_test_restaurant()

    def test_non_tool_call_event(self):
        resp = client.post("/webhook", json={
            "message": {"type": "status-update", "status": "in-progress"}
        })
        assert resp.status_code == 200

    def test_unknown_assistant_returns_error(self):
        payload = {
            "message": {
                "type": "tool-calls",
                "call": {"assistantId": "nonexistent"},
                "toolWithToolCallList": [
                    {
                        "toolCall": {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "check_restaurant_load", "arguments": {}},
                        }
                    }
                ],
            }
        }
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        result = json.loads(body["results"][0]["result"])
        assert "error" in result

    def test_unknown_tool(self):
        result = _webhook_call("nonexistent_tool", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool calls (using Tabit stub for deterministic results)
# ---------------------------------------------------------------------------

class TestToolCalls:
    @pytest.fixture(autouse=True)
    def _ensure_restaurant(self):
        _create_test_restaurant()

    def test_check_restaurant_load(self):
        result = _webhook_call("check_restaurant_load", {})
        assert "level" in result
        assert result["level"] in ("green", "yellow", "red")
        assert "message_he" in result

    def test_transfer_to_human(self):
        result = _webhook_call("transfer_to_human", {
            "reason": "Customer requested human agent"
        })
        assert result["transferred"] is True

    def test_check_availability(self):
        result = _webhook_call("check_availability", {
            "date": "2026-04-10",
            "time": "20:00",
            "party_size": 2,
        })
        assert "is_available" in result
        assert "available_slots" in result

    def test_book_reservation(self):
        result = _webhook_call("book_reservation", {
            "customer_name": "Test User",
            "date": "2026-04-10",
            "time": "20:00",
            "party_size": 4,
        })
        assert "id" in result
        assert result["status"] == "confirmed"


# ---------------------------------------------------------------------------
# Ontopo live integration tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("ONTOPO_LIVE_TESTS") != "1",
    reason="Set ONTOPO_LIVE_TESTS=1 to run live Ontopo API tests",
)
class TestOntopoLive:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.adapters.ontopo import OntopoAdapter
        self.adapter = OntopoAdapter(locale="he", default_city="tel-aviv")
        yield

    @pytest.mark.asyncio
    async def test_search_venue(self):
        venues = await self.adapter.search_venue("taizu")
        assert len(venues) > 0

    @pytest.mark.asyncio
    async def test_check_availability(self):
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        venues = await self.adapter.search_venue("taizu")
        if venues:
            result = await self.adapter.check_availability(
                venue_id=venues[0].id, date=tomorrow, time="20:00", party_size=2,
            )
            assert result.venue_id


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_booking_model(self):
        from src.models import Booking, CustomerInfo
        booking = Booking(
            id="test-1", venue_id="v1", venue_name="Test",
            customer=CustomerInfo(name="Test User", phone="0501234567"),
            date="2026-04-10", time="20:00", party_size=4, status="confirmed",
        )
        assert booking.id == "test-1"

    def test_availability_result(self):
        from src.models import AvailabilityResult, TimeSlot
        result = AvailabilityResult(
            venue_id="v1", venue_name="Test", date="2026-04-10",
            requested_time="20:00", is_available=True,
            available_slots=[TimeSlot(time="20:00", available=True)],
        )
        assert result.is_available


# ---------------------------------------------------------------------------
# Vapi assistant payload
# ---------------------------------------------------------------------------

class TestVapiAssistant:
    def test_payload_structure(self):
        from src.vapi_service import _build_assistant_payload
        payload = _build_assistant_payload("Test Restaurant", "http://localhost:8000")
        assert payload["name"] == "Mia - Test Restaurant"
        assert payload["voice"]["provider"] == "11labs"
        assert payload["transcriber"]["language"] == "he"
        assert len(payload["model"]["tools"]) == 6

    def test_system_prompt_contains_hebrew(self):
        from src.prompts.system_prompt import get_system_prompt
        prompt = get_system_prompt("Test Restaurant")
        assert "מיה" in prompt
        assert "Test Restaurant" in prompt

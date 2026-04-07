"""End-to-end tests for the Restaurant Phone Agent.

Runs against the live FastAPI app (in-process via TestClient) and, optionally,
against the real Ontopo API.

Usage:
    python -m pytest tests/test_agent.py -v
    python -m pytest tests/test_agent.py -v -k ontopo_live   # only live Ontopo tests
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _webhook_call(tool_name: str, arguments: dict) -> dict:
    """Simulate a Vapi tool-call webhook and return parsed results."""
    payload = {
        "message": {
            "type": "tool-calls",
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
        assert "restaurant" in data
        assert "system" in data


# ---------------------------------------------------------------------------
# Webhook routing
# ---------------------------------------------------------------------------

class TestWebhookRouting:
    def test_non_tool_call_event(self):
        """Non-tool-call events should return 200 OK."""
        resp = client.post("/webhook", json={
            "message": {"type": "status-update", "status": "in-progress"}
        })
        assert resp.status_code == 200

    def test_assistant_request_event(self):
        resp = client.post("/webhook", json={
            "message": {"type": "assistant-request"}
        })
        assert resp.status_code == 200

    def test_unknown_tool(self):
        result = _webhook_call("nonexistent_tool", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# Tool calls (using Tabit stub by default for deterministic tests)
# ---------------------------------------------------------------------------

class TestToolCalls:
    """Test all tool calls through the webhook. Uses whichever adapter is
    configured in .env (defaults to ontopo, falls back gracefully)."""

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
        assert "reason" in result


# ---------------------------------------------------------------------------
# Ontopo live integration tests (only run if ONTOPO_LIVE_TESTS=1)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("ONTOPO_LIVE_TESTS") != "1",
    reason="Set ONTOPO_LIVE_TESTS=1 to run live Ontopo API tests",
)
class TestOntopoLive:
    """Tests against the real Ontopo API. Requires network access."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.adapters.ontopo import OntopoAdapter
        self.adapter = OntopoAdapter(locale="he", default_city="tel-aviv")
        yield

    @pytest.mark.asyncio
    async def test_search_venue(self):
        venues = await self.adapter.search_venue("taizu")
        assert len(venues) > 0
        assert venues[0].name

    @pytest.mark.asyncio
    async def test_check_availability(self):
        from datetime import datetime, timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        venues = await self.adapter.search_venue("taizu")
        if venues:
            result = await self.adapter.check_availability(
                venue_id=venues[0].id,
                date=tomorrow,
                time="20:00",
                party_size=2,
            )
            assert result.venue_id
            assert result.date == tomorrow


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_booking_model(self):
        from src.models import Booking, CustomerInfo
        booking = Booking(
            id="test-1",
            venue_id="venue-1",
            venue_name="Test Restaurant",
            customer=CustomerInfo(name="Test User", phone="0501234567"),
            date="2026-04-10",
            time="20:00",
            party_size=4,
            status="confirmed",
        )
        assert booking.id == "test-1"
        data = booking.model_dump()
        assert data["customer"]["name"] == "Test User"

    def test_availability_result(self):
        from src.models import AvailabilityResult, TimeSlot
        result = AvailabilityResult(
            venue_id="v1",
            venue_name="Test",
            date="2026-04-10",
            requested_time="20:00",
            is_available=True,
            available_slots=[
                TimeSlot(time="19:30", available=True),
                TimeSlot(time="20:00", available=True),
                TimeSlot(time="20:30", available=True),
            ],
        )
        assert len(result.available_slots) == 3
        assert result.is_available


# ---------------------------------------------------------------------------
# Vapi assistant payload
# ---------------------------------------------------------------------------

class TestVapiAssistant:
    def test_payload_structure(self):
        from src.vapi_assistant import _build_assistant_payload
        payload = _build_assistant_payload("http://localhost:8000/webhook")
        assert payload["name"].startswith("Mia")
        assert payload["voice"]["provider"] == "11labs"
        assert payload["transcriber"]["language"] == "he"
        assert len(payload["model"]["tools"]) == 6
        assert payload["serverUrl"] == "http://localhost:8000/webhook"

    def test_system_prompt_contains_hebrew(self):
        from src.prompts.system_prompt import get_system_prompt
        prompt = get_system_prompt("Test Restaurant")
        assert "מיה" in prompt
        assert "Test Restaurant" in prompt
        assert "הזמנת שולחן" in prompt

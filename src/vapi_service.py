"""Vapi API service — create, update, and delete assistants programmatically."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings
from src.prompts.system_prompt import get_system_prompt
from src.tools.definitions import TOOLS

logger = logging.getLogger(__name__)

VAPI_BASE = "https://api.vapi.ai"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.vapi_api_key}",
        "Content-Type": "application/json",
    }


def _build_assistant_payload(restaurant_name: str, server_url: str) -> dict[str, Any]:
    """Build the Vapi assistant creation/update payload for a given restaurant."""
    system_prompt = get_system_prompt(restaurant_name)

    return {
        "name": f"Mia - {restaurant_name}",
        "voice": {
            "provider": "11labs",
            "voiceId": settings.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM",
            "model": "eleven_multilingual_v2",
            "stability": 0.6,
            "similarityBoost": 0.8,
            "speed": 1.0,
            "inputPreprocessingEnabled": False,
            "chunkPlan": {"formatPlan": {"enabled": False}},
        },
        "transcriber": {
            "provider": "deepgram",
            "language": "he",
            "model": "nova-2",
        },
        "model": {
            "provider": "openai",
            "model": "gpt-4o",
            "temperature": 0.3,
            "messages": [{"role": "system", "content": system_prompt}],
            "tools": TOOLS,
        },
        "firstMessage": (
            f"שלום! הגעת למסעדת {restaurant_name}. "
            "אני מיה, כאן לעזור לך. במה אני יכולה לסייע לך היום?"
        ),
        "serverUrl": f"{server_url}/webhook",
        "endCallMessage": "תודה שהתקשרת! נשמח לראות אותך. יום נעים!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "backgroundSound": "off",
        "hipaaEnabled": False,
        "recordingEnabled": True,
    }


async def create_assistant(restaurant_name: str) -> dict[str, Any]:
    """Create a new Vapi assistant and return the full response dict.

    Raises RuntimeError on failure.
    """
    payload = _build_assistant_payload(restaurant_name, settings.server_url)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{VAPI_BASE}/assistant", json=payload, headers=_headers()
        )
    if resp.status_code == 201:
        data = resp.json()
        logger.info("Created Vapi assistant id=%s for '%s'", data.get("id"), restaurant_name)
        return data
    raise RuntimeError(f"Vapi create failed ({resp.status_code}): {resp.text}")


async def update_assistant(assistant_id: str, restaurant_name: str) -> dict[str, Any]:
    """Update an existing Vapi assistant. Returns the updated dict."""
    payload = _build_assistant_payload(restaurant_name, settings.server_url)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(
            f"{VAPI_BASE}/assistant/{assistant_id}",
            json=payload,
            headers=_headers(),
        )
    if resp.status_code == 200:
        data = resp.json()
        logger.info("Updated Vapi assistant id=%s", assistant_id)
        return data
    raise RuntimeError(f"Vapi update failed ({resp.status_code}): {resp.text}")


async def delete_assistant(assistant_id: str) -> bool:
    """Delete a Vapi assistant. Returns True on success."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"{VAPI_BASE}/assistant/{assistant_id}", headers=_headers()
        )
    if resp.status_code in (200, 204):
        logger.info("Deleted Vapi assistant id=%s", assistant_id)
        return True
    logger.warning("Vapi delete failed (%s): %s", resp.status_code, resp.text)
    return False

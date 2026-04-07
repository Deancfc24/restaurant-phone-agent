"""Create or update the Vapi assistant for Mia.

Run this script to register the assistant, tools, and voice configuration
with Vapi.  It uses the Vapi REST API directly (no SDK dependency).

Usage:
    python -m src.vapi_assistant             # create new assistant
    python -m src.vapi_assistant --update ID  # update existing assistant

Environment variables required:
    VAPI_API_KEY        — your Vapi dashboard API key
    ELEVENLABS_VOICE_ID — the ElevenLabs voice ID for Hebrew TTS (optional)
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from config import settings
from src.prompts.system_prompt import get_system_prompt
from src.tools.definitions import TOOLS

VAPI_BASE = "https://api.vapi.ai"


def _build_assistant_payload(server_url: str) -> dict:
    """Assemble the full assistant creation/update payload."""
    system_prompt = get_system_prompt(settings.restaurant_name)

    voice_config: dict = {
        "provider": "11labs",
        "voiceId": settings.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM",
        "model": "eleven_multilingual_v2",
        "stability": 0.6,
        "similarityBoost": 0.8,
        "speed": 1.0,
        "inputPreprocessingEnabled": False,
        "chunkPlan": {
            "formatPlan": {
                "enabled": False,
            }
        },
    }

    transcriber_config: dict = {
        "provider": "deepgram",
        "language": "he",
        "model": "nova-2",
    }

    model_config: dict = {
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            }
        ],
        "tools": TOOLS,
    }

    payload: dict = {
        "name": f"Mia - {settings.restaurant_name}",
        "voice": voice_config,
        "transcriber": transcriber_config,
        "model": model_config,
        "firstMessage": f"שלום! הגעת למסעדת {settings.restaurant_name}. אני מיה, כאן לעזור לך. במה אני יכולה לסייע לך היום?",
        "serverUrl": server_url,
        "endCallMessage": "תודה שהתקשרת! נשמח לראות אותך. יום נעים!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "backgroundSound": "off",
        "hipaaEnabled": False,
        "recordingEnabled": True,
    }

    return payload


def create_assistant(server_url: str) -> dict:
    api_key = settings.vapi_api_key
    if not api_key:
        print("Error: VAPI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    payload = _build_assistant_payload(server_url)

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{VAPI_BASE}/assistant",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code == 201:
        data = resp.json()
        print(f"Assistant created successfully!")
        print(f"  ID:   {data.get('id')}")
        print(f"  Name: {data.get('name')}")
        return data
    else:
        print(f"Error creating assistant: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


def update_assistant(assistant_id: str, server_url: str) -> dict:
    api_key = settings.vapi_api_key
    if not api_key:
        print("Error: VAPI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    payload = _build_assistant_payload(server_url)

    with httpx.Client(timeout=30.0) as client:
        resp = client.patch(
            f"{VAPI_BASE}/assistant/{assistant_id}",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code == 200:
        data = resp.json()
        print(f"Assistant updated successfully!")
        print(f"  ID:   {data.get('id')}")
        print(f"  Name: {data.get('name')}")
        return data
    else:
        print(f"Error updating assistant: {resp.status_code}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update the Vapi assistant for Mia")
    parser.add_argument(
        "--update",
        metavar="ASSISTANT_ID",
        help="Update an existing assistant by ID instead of creating a new one",
    )
    parser.add_argument(
        "--server-url",
        default="https://your-server.example.com/webhook",
        help="The public URL where the webhook server is reachable",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload without sending it to Vapi",
    )
    args = parser.parse_args()

    if args.dry_run:
        payload = _build_assistant_payload(args.server_url)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if args.update:
        update_assistant(args.update, args.server_url)
    else:
        create_assistant(args.server_url)


if __name__ == "__main__":
    main()

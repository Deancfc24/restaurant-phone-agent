"""CLI to create or update a Vapi assistant.

This script wraps src/vapi_service.py for command-line usage.
In normal operation the dashboard handles assistant lifecycle automatically.

Usage:
    python -m src.vapi_assistant --dry-run --name "My Restaurant"
    python -m src.vapi_assistant --name "My Restaurant"
    python -m src.vapi_assistant --update ASSISTANT_ID --name "My Restaurant"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from config import settings
from src.vapi_service import _build_assistant_payload, create_assistant, update_assistant


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update a Vapi assistant for Mia")
    parser.add_argument("--name", default="My Restaurant", help="Restaurant name")
    parser.add_argument("--update", metavar="ASSISTANT_ID", help="Update an existing assistant")
    parser.add_argument("--server-url", default=None, help="Override the server URL")
    parser.add_argument("--dry-run", action="store_true", help="Print payload only")
    args = parser.parse_args()

    server_url = args.server_url or settings.server_url

    if args.dry_run:
        payload = _build_assistant_payload(args.name, server_url)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if not settings.vapi_api_key:
        print("Error: VAPI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    if args.update:
        data = asyncio.run(update_assistant(args.update, args.name))
    else:
        data = asyncio.run(create_assistant(args.name))

    print(f"  ID:   {data.get('id')}")
    print(f"  Name: {data.get('name')}")


if __name__ == "__main__":
    main()

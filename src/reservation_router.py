"""Routes tool calls to the appropriate reservation adapter.

Provides a single entry-point (``handle_tool_call``) that the webhook server
invokes.  The router reads the restaurant configuration to decide which adapter
(Ontopo / Tabit) to use, then delegates the call and serialises the response.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config import settings
from src.adapters.base import ReservationAdapter
from src.adapters.ontopo import OntopoAdapter
from src.adapters.tabit import TabitAdapter
from src.models import CustomerInfo, SpecialRequest

logger = logging.getLogger(__name__)

_adapter: ReservationAdapter | None = None


def get_adapter() -> ReservationAdapter:
    """Lazily initialise and return the configured adapter."""
    global _adapter
    if _adapter is not None:
        return _adapter

    system = settings.reservation_system.lower()
    if system == "ontopo":
        _adapter = OntopoAdapter(
            locale="he",
            default_city=settings.restaurant_city,
        )
    elif system == "tabit":
        _adapter = TabitAdapter(
            organization_id=settings.tabit_organization_id,
            api_key=settings.tabit_api_key,
        )
    else:
        raise ValueError(f"Unknown reservation system: {system}")

    logger.info("Initialised %s adapter for restaurant '%s'", system, settings.restaurant_name)
    return _adapter


async def shutdown_adapter() -> None:
    global _adapter
    if _adapter is not None:
        await _adapter.close()
        _adapter = None


async def handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call and return a JSON-encoded string result.

    Returns a serialised dict so Vapi can pass it to the LLM as tool output.
    """
    adapter = get_adapter()
    venue_id = settings.restaurant_venue_id

    try:
        if name == "check_availability":
            result = await adapter.check_availability(
                venue_id=venue_id,
                date=arguments["date"],
                time=arguments["time"],
                party_size=arguments["party_size"],
            )
            return result.model_dump_json()

        elif name == "book_reservation":
            customer = CustomerInfo(
                name=arguments["customer_name"],
                phone=arguments.get("customer_phone"),
            )
            special = None
            if sr := arguments.get("special_requests"):
                special = SpecialRequest(**sr)

            result = await adapter.book_reservation(
                venue_id=venue_id,
                date=arguments["date"],
                time=arguments["time"],
                party_size=arguments["party_size"],
                customer=customer,
                special_requests=special,
            )
            return result.model_dump_json()

        elif name == "find_reservation":
            results = await adapter.find_reservation(
                customer_name=arguments["customer_name"],
                date=arguments.get("date"),
                customer_phone=arguments.get("customer_phone"),
            )
            return json.dumps(
                [b.model_dump(mode="json") for b in results],
                ensure_ascii=False,
            )

        elif name == "cancel_reservation":
            success = await adapter.cancel_reservation(
                reservation_id=arguments["reservation_id"],
            )
            return json.dumps({"success": success, "reservation_id": arguments["reservation_id"]})

        elif name == "check_restaurant_load":
            result = await adapter.get_restaurant_load(venue_id)
            return result.model_dump_json()

        elif name == "transfer_to_human":
            reason = arguments.get("reason", "")
            logger.info("Transfer to human requested: %s", reason)
            return json.dumps({
                "transferred": True,
                "reason": reason,
                "message": "מעבירה לנציג אנושי.",
            })

        else:
            logger.warning("Unknown tool call: %s", name)
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception:
        logger.exception("Error handling tool call %s", name)
        return json.dumps({
            "error": "שגיאת מערכת. אנא נסו שוב.",
            "tool": name,
        })

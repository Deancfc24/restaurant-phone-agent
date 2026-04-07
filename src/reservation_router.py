"""Routes tool calls to the appropriate reservation adapter.

Refactored for multi-restaurant: adapters are created per-restaurant based on
database configuration, rather than using a global singleton.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.adapters.base import ReservationAdapter
from src.adapters.ontopo import OntopoAdapter
from src.adapters.tabit import TabitAdapter
from src.database import Restaurant
from src.models import CustomerInfo, SpecialRequest

logger = logging.getLogger(__name__)

# Cache adapters by restaurant id to avoid re-creating on every call
_adapter_cache: dict[str, ReservationAdapter] = {}


def get_adapter_for_restaurant(restaurant: Restaurant) -> ReservationAdapter:
    """Return (or create) the adapter for a specific restaurant."""
    if restaurant.id in _adapter_cache:
        return _adapter_cache[restaurant.id]

    system = restaurant.reservation_system.lower()
    if system == "ontopo":
        adapter = OntopoAdapter(locale="he", default_city=restaurant.city)
    elif system == "tabit":
        adapter = TabitAdapter(
            organization_id=restaurant.tabit_organization_id,
            api_key=restaurant.tabit_api_key,
        )
    else:
        raise ValueError(f"Unknown reservation system: {system}")

    _adapter_cache[restaurant.id] = adapter
    logger.info("Created %s adapter for '%s'", system, restaurant.name)
    return adapter


def invalidate_adapter(restaurant_id: str) -> None:
    """Remove a cached adapter (call after restaurant config changes)."""
    _adapter_cache.pop(restaurant_id, None)


async def shutdown_all_adapters() -> None:
    """Close all cached adapters (called on app shutdown)."""
    for adapter in _adapter_cache.values():
        await adapter.close()
    _adapter_cache.clear()


async def handle_tool_call(
    restaurant: Restaurant, name: str, arguments: dict[str, Any]
) -> str:
    """Dispatch a tool call for a specific restaurant.

    Returns a JSON-encoded string result for Vapi.
    """
    adapter = get_adapter_for_restaurant(restaurant)
    venue_id = restaurant.venue_id

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
            logger.info("Transfer to human requested for '%s': %s", restaurant.name, reason)
            return json.dumps({
                "transferred": True,
                "reason": reason,
                "message": "מעבירה לנציג אנושי.",
            })

        else:
            logger.warning("Unknown tool call: %s", name)
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception:
        logger.exception("Error handling tool call %s for '%s'", name, restaurant.name)
        return json.dumps({
            "error": "שגיאת מערכת. אנא נסו שוב.",
            "tool": name,
        })

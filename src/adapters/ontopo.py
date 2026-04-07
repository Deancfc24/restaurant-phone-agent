"""Ontopo reservation system adapter.

Integrates with the Ontopo API (https://ontopo.com/api) to search restaurants,
check availability, and generate booking links.  Based on patterns from the
open-source agent-skill-ontopo project.

Limitations:
  - Ontopo's public API does not support *placing* reservations directly.
    book_reservation() returns a booking URL that the customer can use.
  - find_reservation() and cancel_reservation() are not supported by the
    public API; they return stub responses.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from src.adapters.base import ReservationAdapter
from src.models import (
    AvailabilityResult,
    Booking,
    CustomerInfo,
    LoadLevel,
    RestaurantLoad,
    SpecialRequest,
    TimeSlot,
    Venue,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://ontopo.com/api"
WEBSITE_URL = "https://ontopo.com"
ISRAEL_DISTRIBUTOR_SLUG = "15171493"

CITY_DATA: dict[str, tuple[str, str, str]] = {
    "tel-aviv": ("29421469", "telavivjaffa", "תל אביב"),
    "jerusalem": ("29384685", "jerusalem", "ירושלים"),
    "haifa": ("11243454", "haifa", "חיפה"),
    "herzeliya": ("62204663", "herzeliya", "הרצליה"),
    "raanana": ("71499188", "raanana", "רעננה"),
    "ramatgan": ("87918421", "rag-giv-area", "רמת גן - גבעתיים"),
    "natanya": ("19467447", "netanya_area", "נתניה"),
    "ashdod": ("93786391", "ashdod", "אשדוד"),
    "beer-sheva": ("83166822", "beer_sheva", "באר שבע"),
    "eilat": ("71154151", "eilat_area", "אילת"),
    "modiin": ("49473533", "modiin_area", "מודיעין והסביבה"),
    "rehovot": ("58943955", "rehovot", "רחובות"),
    "rishon_lezion": ("39514882", "rishon_lezion", "ראשון לציון"),
    "petah_tikva": ("74902764", "petah_tikva_area", "פתח תקווה"),
    "holon": ("60235869", "holon-batyam-area", "חולון - בת ים"),
    "kfar_saba": ("45164735", "kfarsaba", "כפר סבא"),
    "hod_hasharon": ("77097784", "hod_hasharon", "הוד השרון"),
    "ramat_hasharon": ("64031461", "ramat_hasharon", "רמת השרון"),
    "caesarya": ("86032396", "caesarea_area", "קיסריה - חדרה והסביבה"),
    "ness_ziona": ("47865336", "ness_ziona", "נס ציונה"),
    "kiryat_ono": ("29033809", "kiryat_ono_area", "קריית אונו"),
    "kineret": ("92127549", "golan_kineret", "כנרת ורמת הגולן"),
    "the_north": ("45577648", "the_north", "אזור הצפון"),
    "south": ("65424368", "south", "אזור הדרום"),
    "merkaz": ("41581793", "merkaz", "אזור המרכז"),
    "hashfela": ("74908782", "hashfela", "אזור השפלה"),
    "hasharon": ("75635900", "hasharon", "אזור השרון"),
}

CITY_ALIASES: dict[str, str] = {
    "herzliya": "herzeliya",
    "ramat-gan": "ramatgan",
    "netanya": "natanya",
    "rishon-lezion": "rishon_lezion",
    "petah-tikva": "petah_tikva",
    "kfar-saba": "kfar_saba",
    "hod-hasharon": "hod_hasharon",
    "ramat-hasharon": "ramat_hasharon",
    "caesarea": "caesarya",
    "ness-ziona": "ness_ziona",
    "kiryat-ono": "kiryat_ono",
    "north": "the_north",
    "bat-yam": "holon",
}


def _resolve_city(city: str) -> str:
    city = city.lower().strip()
    return CITY_ALIASES.get(city, city)


def _to_api_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD."""
    return date_str.replace("-", "")


def _to_api_time(time_str: str) -> str:
    """Convert HH:MM to HHMM."""
    return time_str.replace(":", "")


def _from_api_time(time_str: str) -> str:
    """Convert HHMM to HH:MM."""
    if len(time_str) == 4:
        return f"{time_str[:2]}:{time_str[2:]}"
    return time_str


class OntopoAdapter(ReservationAdapter):
    """Adapter for the Ontopo restaurant reservation platform."""

    def __init__(self, locale: str = "he", default_city: str = "tel-aviv"):
        self.locale = locale
        self.default_city = _resolve_city(default_city)
        self._token: str | None = None
        self._client = httpx.AsyncClient(timeout=30.0)
        self._venue_page_cache: dict[str, str] = {}

    async def _ensure_auth(self) -> None:
        if self._token:
            return
        resp = await self._request("POST", "/loginAnonymously", auth_required=False)
        self._token = resp.get("jwt_token")
        if not self._token:
            raise RuntimeError("Failed to obtain Ontopo authentication token")

    async def _request(
        self,
        method: str,
        endpoint: str,
        body: dict | None = None,
        params: dict | None = None,
        auth_required: bool = True,
        retries: int = 3,
    ) -> Any:
        if auth_required:
            await self._ensure_auth()

        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_required and self._token:
            headers["token"] = self._token

        for attempt in range(retries):
            try:
                if method == "GET":
                    response = await self._client.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = await self._client.post(url, json=body, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                if response.status_code == 429:
                    await asyncio.sleep(2**attempt)
                    continue
                if response.status_code == 401:
                    self._token = None
                    await self._ensure_auth()
                    continue

                response.raise_for_status()
                return response.json() if response.content else {}

            except httpx.HTTPStatusError as exc:
                if attempt == retries - 1:
                    raise RuntimeError(
                        f"Ontopo API error: {exc.response.status_code}"
                    ) from exc
                await asyncio.sleep(1)
            except httpx.RequestError as exc:
                if attempt == retries - 1:
                    raise RuntimeError(f"Ontopo network error: {exc}") from exc
                await asyncio.sleep(1)

        raise RuntimeError("Max retries exceeded")

    async def _resolve_page_id(self, venue_id: str) -> str:
        if venue_id in self._venue_page_cache:
            return self._venue_page_cache[venue_id]
        try:
            profile = await self._request(
                "GET",
                "/venue_profile",
                params={"slug": venue_id, "version": "1", "locale": self.locale},
                auth_required=False,
            )
            for page in profile.get("pages", []):
                if page.get("content_type") == "reservation":
                    slug = page.get("slug", page.get("id", venue_id))
                    self._venue_page_cache[venue_id] = slug
                    return slug
            pages = profile.get("pages", [])
            if pages:
                slug = pages[0].get("slug", pages[0].get("id", venue_id))
                self._venue_page_cache[venue_id] = slug
                return slug
        except Exception:
            logger.warning("Could not resolve page_id for venue %s", venue_id)

        self._venue_page_cache[venue_id] = venue_id
        return venue_id

    # ---- ReservationAdapter interface ----

    async def search_venue(self, query: str) -> list[Venue]:
        params = {
            "slug": ISRAEL_DISTRIBUTOR_SLUG,
            "version": "1",
            "terms": query,
            "locale": self.locale,
        }
        response = await self._request(
            "GET", "/venue_search", params=params, auth_required=False
        )
        raw = response if isinstance(response, list) else response.get("venues", response.get("results", []))
        if not isinstance(raw, list):
            raw = []

        venues: list[Venue] = []
        for v in raw[:10]:
            venues.append(
                Venue(
                    id=str(v.get("slug", v.get("id", ""))),
                    name=v.get("title", v.get("name", "Unknown")),
                    address=v.get("address"),
                    city=v.get("city"),
                    cuisine=v.get("cuisine"),
                    system="ontopo",
                )
            )
        return venues

    async def check_availability(
        self,
        venue_id: str,
        date: str,
        time: str,
        party_size: int,
    ) -> AvailabilityResult:
        page_id = await self._resolve_page_id(venue_id)
        api_date = _to_api_date(date)
        api_time = _to_api_time(time)

        result = await self._request(
            "POST",
            "/availability_search",
            body={
                "slug": page_id,
                "locale": self.locale,
                "criteria": {
                    "size": str(party_size),
                    "date": api_date,
                    "time": api_time,
                },
            },
        )

        slots: list[TimeSlot] = []
        has_exact = False

        for area in result.get("areas", []):
            area_name = area.get("name", "")
            for opt in area.get("options", []):
                method = opt.get("method", "")
                opt_time = opt.get("time", "")
                if not opt_time:
                    continue

                display_time = _from_api_time(opt_time)
                if method == "seat":
                    note = f"אזור: {area_name}" if area_name else None
                    slots.append(TimeSlot(time=display_time, available=True, notes=note))
                    if display_time == time:
                        has_exact = True
                elif method == "standby":
                    slots.append(
                        TimeSlot(
                            time=display_time,
                            available=True,
                            notes=f"רשימת המתנה – {area_name}" if area_name else "רשימת המתנה",
                        )
                    )

        is_available = has_exact or len(slots) > 0

        if not slots:
            message = "לא נמצאו שולחנות פנויים לשעה המבוקשת."
        elif has_exact:
            message = f"יש שולחן פנוי בשעה {time}!"
        else:
            alt_times = ", ".join(s.time for s in slots[:4])
            message = f"השעה {time} אינה זמינה. שעות חלופיות: {alt_times}"

        return AvailabilityResult(
            venue_id=venue_id,
            venue_name=venue_id,
            date=date,
            requested_time=time,
            is_available=is_available,
            available_slots=slots,
            message=message,
        )

    async def book_reservation(
        self,
        venue_id: str,
        date: str,
        time: str,
        party_size: int,
        customer: CustomerInfo,
        special_requests: SpecialRequest | None = None,
    ) -> Booking:
        """Generate a booking via Ontopo.

        Note: the public Ontopo API does not support placing reservations directly.
        We return a booking URL that the customer can use to complete the reservation
        on the Ontopo website. In production this could be enhanced with browser
        automation or an official Ontopo partner API.
        """
        api_date = _to_api_date(date)
        api_time = _to_api_time(time)
        page_id = await self._resolve_page_id(venue_id)

        booking_url = (
            f"{WEBSITE_URL}/he/il/page/{page_id}/booking"
            f"?date={api_date}&time={api_time}&size={party_size}"
        )

        booking_id = f"ontopo-{venue_id}-{api_date}-{api_time}-{customer.name.replace(' ', '_')}"

        return Booking(
            id=booking_id,
            venue_id=venue_id,
            venue_name=venue_id,
            customer=customer,
            date=date,
            time=time,
            party_size=party_size,
            special_requests=special_requests,
            status="pending_confirmation",
            booking_url=booking_url,
            created_at=datetime.now(),
        )

    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Not supported via the public Ontopo API."""
        logger.warning(
            "cancel_reservation is not supported by the Ontopo public API. "
            "Reservation %s was NOT cancelled in the system.",
            reservation_id,
        )
        return False

    async def find_reservation(
        self,
        customer_name: str,
        date: str | None = None,
        customer_phone: str | None = None,
    ) -> list[Booking]:
        """Not supported via the public Ontopo API."""
        logger.warning(
            "find_reservation is not supported by the Ontopo public API."
        )
        return []

    async def get_restaurant_load(self, venue_id: str) -> RestaurantLoad:
        """Estimate load by checking availability for the current time slot.

        This is a heuristic: we check how many slots are available right now.
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        try:
            availability = await self.check_availability(venue_id, date_str, time_str, 2)
            num_slots = len(availability.available_slots)

            if num_slots >= 5:
                return RestaurantLoad(
                    venue_id=venue_id,
                    level=LoadLevel.GREEN,
                    message_he="המסעדה לא מלאה כרגע. השולחן שמור לכם, אין ממה לדאוג!",
                    hold_minutes=None,
                )
            elif num_slots >= 2:
                return RestaurantLoad(
                    venue_id=venue_id,
                    level=LoadLevel.YELLOW,
                    message_he="המסעדה עמוסה באופן בינוני. נוכל לשמור את השולחן עד 15 דקות.",
                    hold_minutes=15,
                )
            else:
                return RestaurantLoad(
                    venue_id=venue_id,
                    level=LoadLevel.RED,
                    message_he="המסעדה מלאה כרגע. נוכל לשמור את השולחן עד 10 דקות בלבד.",
                    hold_minutes=10,
                )
        except Exception:
            logger.exception("Failed to estimate restaurant load for %s", venue_id)
            return RestaurantLoad(
                venue_id=venue_id,
                level=LoadLevel.YELLOW,
                message_he="לא הצלחתי לבדוק את העומס כרגע. ננסה לשמור את השולחן.",
                hold_minutes=15,
            )

    async def close(self) -> None:
        await self._client.aclose()

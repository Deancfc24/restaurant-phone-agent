"""Tabit reservation system adapter (stub implementation).

Tabit (https://tabit.cloud) is one of Israel's leading restaurant management
platforms.  However, there is no publicly documented developer API for
reservation management.

This adapter provides the full ReservationAdapter interface with mock/stub
responses.  When Tabit API access is obtained (via partnership or reverse
engineering), the private methods can be replaced with real HTTP calls.

Known API surface (from public CVE disclosures):
  - tgm-api.tabit.cloud/rsv/management/{reservationId}?organization={orgId}
  - reservations.tabit.cloud  (web booking frontend)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

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

# In-memory store for mock bookings (replaced by Tabit API in production)
_mock_bookings: dict[str, Booking] = {}


class TabitAdapter(ReservationAdapter):
    """Stub adapter for the Tabit restaurant platform.

    All methods return plausible mock data.  Replace the internals with real
    Tabit API calls once access is available.
    """

    def __init__(self, organization_id: str = "", api_key: str = ""):
        self.organization_id = organization_id
        self.api_key = api_key
        logger.info(
            "TabitAdapter initialized in STUB mode. "
            "Real Tabit API integration requires API credentials from Tabit."
        )

    async def search_venue(self, query: str) -> list[Venue]:
        logger.info("Tabit search_venue (stub): query=%s", query)
        return [
            Venue(
                id=f"tabit-{self.organization_id or 'demo'}",
                name=query,
                address="",
                city="",
                system="tabit",
            )
        ]

    async def check_availability(
        self,
        venue_id: str,
        date: str,
        time: str,
        party_size: int,
    ) -> AvailabilityResult:
        """Return mock availability with slots around the requested time."""
        logger.info(
            "Tabit check_availability (stub): venue=%s date=%s time=%s size=%d",
            venue_id, date, time, party_size,
        )
        hour, minute = map(int, time.split(":"))
        slots = []
        for delta in [-1, 0, 1]:
            slot_hour = hour + delta
            if 11 <= slot_hour <= 23:
                slots.append(
                    TimeSlot(time=f"{slot_hour:02d}:{minute:02d}", available=True)
                )

        exact_available = any(s.time == time for s in slots)

        return AvailabilityResult(
            venue_id=venue_id,
            venue_name=venue_id,
            date=date,
            requested_time=time,
            is_available=exact_available,
            available_slots=slots,
            message="יש שולחן פנוי!" if exact_available else f"השעה {time} אינה זמינה.",
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
        logger.info(
            "Tabit book_reservation (stub): venue=%s date=%s time=%s size=%d customer=%s",
            venue_id, date, time, party_size, customer.name,
        )
        booking_id = f"tabit-{uuid.uuid4().hex[:8]}"
        booking = Booking(
            id=booking_id,
            venue_id=venue_id,
            venue_name=venue_id,
            customer=customer,
            date=date,
            time=time,
            party_size=party_size,
            special_requests=special_requests,
            status="confirmed",
            booking_url=f"https://reservations.tabit.cloud/{self.organization_id}/booking/{booking_id}",
            created_at=datetime.now(),
        )
        _mock_bookings[booking_id] = booking
        return booking

    async def cancel_reservation(self, reservation_id: str) -> bool:
        logger.info("Tabit cancel_reservation (stub): id=%s", reservation_id)
        if reservation_id in _mock_bookings:
            _mock_bookings[reservation_id].status = "cancelled"
            return True
        return False

    async def find_reservation(
        self,
        customer_name: str,
        date: str | None = None,
        customer_phone: str | None = None,
    ) -> list[Booking]:
        logger.info(
            "Tabit find_reservation (stub): name=%s date=%s phone=%s",
            customer_name, date, customer_phone,
        )
        results: list[Booking] = []
        name_lower = customer_name.lower()
        for booking in _mock_bookings.values():
            if booking.customer.name.lower() == name_lower:
                if date and booking.date != date:
                    continue
                if customer_phone and booking.customer.phone != customer_phone:
                    continue
                results.append(booking)
        return results

    async def get_restaurant_load(self, venue_id: str) -> RestaurantLoad:
        logger.info("Tabit get_restaurant_load (stub): venue=%s", venue_id)
        return RestaurantLoad(
            venue_id=venue_id,
            level=LoadLevel.GREEN,
            message_he="המסעדה לא מלאה כרגע. השולחן שמור לכם!",
            hold_minutes=None,
        )

    async def close(self) -> None:
        pass

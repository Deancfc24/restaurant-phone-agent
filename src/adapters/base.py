"""Abstract base class for reservation system adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import (
    AvailabilityResult,
    Booking,
    CustomerInfo,
    RestaurantLoad,
    SpecialRequest,
    Venue,
)


class ReservationAdapter(ABC):
    """Unified interface for restaurant reservation systems (Ontopo, Tabit, etc.)."""

    @abstractmethod
    async def search_venue(self, query: str) -> list[Venue]:
        """Search for venues by name or keyword."""

    @abstractmethod
    async def check_availability(
        self,
        venue_id: str,
        date: str,
        time: str,
        party_size: int,
    ) -> AvailabilityResult:
        """Check availability for a specific date/time/party size.

        Args:
            venue_id: Venue identifier in the reservation system.
            date: Date in YYYY-MM-DD format.
            time: Time in HH:MM format (24h).
            party_size: Number of guests.

        Returns:
            AvailabilityResult with available slots and status.
        """

    @abstractmethod
    async def book_reservation(
        self,
        venue_id: str,
        date: str,
        time: str,
        party_size: int,
        customer: CustomerInfo,
        special_requests: SpecialRequest | None = None,
    ) -> Booking:
        """Create a reservation.

        Args:
            venue_id: Venue identifier in the reservation system.
            date: Date in YYYY-MM-DD format.
            time: Time in HH:MM format (24h).
            party_size: Number of guests.
            customer: Customer contact info.
            special_requests: Optional special requests.

        Returns:
            Booking confirmation with ID and details.
        """

    @abstractmethod
    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel an existing reservation.

        Returns:
            True if successfully cancelled.
        """

    @abstractmethod
    async def find_reservation(
        self,
        customer_name: str,
        date: str | None = None,
        customer_phone: str | None = None,
    ) -> list[Booking]:
        """Look up reservations by customer name and optionally date/phone.

        Returns:
            List of matching bookings.
        """

    @abstractmethod
    async def get_restaurant_load(self, venue_id: str) -> RestaurantLoad:
        """Get current restaurant occupancy / pressure level.

        Returns:
            RestaurantLoad with green/yellow/red level and hold guidance.
        """

    async def close(self) -> None:
        """Clean up resources (HTTP clients, etc.). Override if needed."""

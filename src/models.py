from __future__ import annotations

from datetime import date, time, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LoadLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ReservationSystem(str, Enum):
    ONTOPO = "ontopo"
    TABIT = "tabit"


class Venue(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    cuisine: Optional[str] = None
    phone: Optional[str] = None
    system: ReservationSystem


class TimeSlot(BaseModel):
    time: str = Field(description="HH:MM format")
    available: bool = True
    notes: Optional[str] = None


class AvailabilityResult(BaseModel):
    venue_id: str
    venue_name: str
    date: str = Field(description="YYYY-MM-DD format")
    requested_time: str = Field(description="HH:MM format")
    is_available: bool
    available_slots: list[TimeSlot] = Field(default_factory=list)
    message: Optional[str] = None


class CustomerInfo(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class SpecialRequest(BaseModel):
    highchair: bool = False
    birthday: bool = False
    allergies: Optional[str] = None
    seating_preference: Optional[str] = None
    other: Optional[str] = None


class Booking(BaseModel):
    id: str
    venue_id: str
    venue_name: str
    customer: CustomerInfo
    date: str = Field(description="YYYY-MM-DD format")
    time: str = Field(description="HH:MM format")
    party_size: int
    special_requests: Optional[SpecialRequest] = None
    status: str = "confirmed"
    booking_url: Optional[str] = None
    created_at: Optional[datetime] = None


class RestaurantLoad(BaseModel):
    venue_id: str
    level: LoadLevel
    message_he: str = Field(description="Hebrew message describing the load level")
    hold_minutes: Optional[int] = Field(
        None,
        description="How many minutes the table can be held (None = unlimited)",
    )


# --- Vapi webhook models ---


class VapiToolCallFunction(BaseModel):
    name: str
    arguments: dict


class VapiToolCall(BaseModel):
    id: str
    type: str = "function"
    function: VapiToolCallFunction


class VapiToolWithToolCall(BaseModel):
    toolCallId: Optional[str] = None
    tool: Optional[dict] = None
    toolCall: VapiToolCall


class VapiToolCallsMessage(BaseModel):
    type: str
    toolWithToolCallList: list[VapiToolWithToolCall] = Field(default_factory=list)


class VapiWebhookPayload(BaseModel):
    message: VapiToolCallsMessage


class VapiToolResult(BaseModel):
    name: str
    toolCallId: str
    result: str = Field(description="JSON-encoded string result")


class VapiWebhookResponse(BaseModel):
    results: list[VapiToolResult]

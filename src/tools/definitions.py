"""Vapi tool (function) definitions for the restaurant phone agent.

Each tool follows the OpenAI-compatible function-calling schema that Vapi expects.
These are registered on the Vapi assistant so the LLM can invoke them mid-conversation,
and the webhook server fulfills them.
"""

from __future__ import annotations

TOOLS: list[dict] = [
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "רגע, אני בודקת את הזמינות...",
            },
            {
                "type": "request-complete",
                "content": "מצאתי את המידע.",
            },
            {
                "type": "request-failed",
                "content": "סליחה, נתקלתי בבעיה. אנסה שוב.",
            },
        ],
        "function": {
            "name": "check_availability",
            "description": (
                "Check table availability at the restaurant for a specific date, "
                "time, and party size. Returns available time slots."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Requested date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Requested time in HH:MM format (24-hour)",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of guests",
                    },
                },
                "required": ["date", "time", "party_size"],
            },
        },
    },
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "רגע, אני מבצעת את ההזמנה...",
            },
            {
                "type": "request-complete",
                "content": "ההזמנה בוצעה בהצלחה!",
            },
            {
                "type": "request-failed",
                "content": "סליחה, לא הצלחתי לבצע את ההזמנה. ננסה שוב.",
            },
        ],
        "function": {
            "name": "book_reservation",
            "description": (
                "Book a table reservation at the restaurant. "
                "Must check availability first before booking."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Full name of the customer making the reservation",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer phone number",
                    },
                    "date": {
                        "type": "string",
                        "description": "Reservation date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Reservation time in HH:MM format (24-hour)",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of guests",
                    },
                    "special_requests": {
                        "type": "object",
                        "description": "Any special requests for the reservation",
                        "properties": {
                            "highchair": {
                                "type": "boolean",
                                "description": "Whether a highchair is needed",
                            },
                            "birthday": {
                                "type": "boolean",
                                "description": "Whether it is a birthday celebration",
                            },
                            "allergies": {
                                "type": "string",
                                "description": "Any food allergies to note",
                            },
                            "seating_preference": {
                                "type": "string",
                                "description": "Seating preference (e.g., indoor, outdoor, bar)",
                            },
                            "other": {
                                "type": "string",
                                "description": "Any other special request",
                            },
                        },
                    },
                },
                "required": ["customer_name", "date", "time", "party_size"],
            },
        },
    },
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "רגע, אני מחפשת את ההזמנה...",
            },
            {
                "type": "request-complete",
                "content": "מצאתי את ההזמנה.",
            },
            {
                "type": "request-failed",
                "content": "סליחה, לא הצלחתי לאתר את ההזמנה.",
            },
        ],
        "function": {
            "name": "find_reservation",
            "description": (
                "Find an existing reservation by the customer's name and optionally "
                "date. Used for cancellation and late arrival flows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Name the reservation is under",
                    },
                    "date": {
                        "type": "string",
                        "description": "Reservation date in YYYY-MM-DD format (optional, helps narrow search)",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer phone number (optional, helps narrow search)",
                    },
                },
                "required": ["customer_name"],
            },
        },
    },
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "רגע, אני מבטלת את ההזמנה...",
            },
            {
                "type": "request-complete",
                "content": "ההזמנה בוטלה.",
            },
            {
                "type": "request-failed",
                "content": "סליחה, לא הצלחתי לבטל את ההזמנה.",
            },
        ],
        "function": {
            "name": "cancel_reservation",
            "description": "Cancel an existing reservation by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {
                        "type": "string",
                        "description": "The unique ID of the reservation to cancel",
                    },
                },
                "required": ["reservation_id"],
            },
        },
    },
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "רגע, אני בודקת את העומס הנוכחי...",
            },
            {
                "type": "request-complete",
                "content": "קיבלתי את המידע.",
            },
            {
                "type": "request-failed",
                "content": "סליחה, לא הצלחתי לבדוק את העומס כרגע.",
            },
        ],
        "function": {
            "name": "check_restaurant_load",
            "description": (
                "Check the current load / pressure level of the restaurant. "
                "Returns green (low), yellow (medium), or red (high) along with "
                "guidance on how long a table can be held."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "messages": [
            {
                "type": "request-start",
                "content": "אני מעבירה אותך עכשיו לנציג אנושי שישמח לעזור לך. רגע בבקשה.",
            },
        ],
        "function": {
            "name": "transfer_to_human",
            "description": (
                "Transfer the call to a human agent. Use only when: "
                "the request is beyond AI capabilities, a system error occurs, "
                "the customer explicitly asks, or after two failed resolution attempts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the transfer",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]

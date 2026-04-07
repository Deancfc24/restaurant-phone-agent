"""FastAPI router for Vapi webhook events.

Vapi sends POST requests to the server URL whenever the assistant invokes a
tool during a call.  This module parses those requests and routes them through
the reservation router.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.reservation_router import handle_tool_call

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def vapi_webhook(request: Request) -> JSONResponse:
    """Handle all Vapi server-URL events.

    Vapi sends several event types (assistant-request, function-call,
    tool-calls, status-update, end-of-call-report, etc.).  We only act on
    ``tool-calls``; everything else is acknowledged with 200 OK.
    """
    payload: dict[str, Any] = await request.json()
    message = payload.get("message", {})
    msg_type = message.get("type", "")

    if msg_type == "tool-calls":
        return await _handle_tool_calls(message)

    if msg_type == "assistant-request":
        return _handle_assistant_request()

    logger.debug("Received Vapi event type=%s (no-op)", msg_type)
    return JSONResponse(content={"ok": True})


async def _handle_tool_calls(message: dict[str, Any]) -> JSONResponse:
    """Process one or more tool calls from Vapi and return results."""
    tool_call_list = message.get("toolWithToolCallList", [])
    results: list[dict[str, str]] = []

    for item in tool_call_list:
        tool_call = item.get("toolCall", {})
        function = tool_call.get("function", {})
        fn_name = function.get("name", "")
        fn_args = function.get("arguments", {})
        call_id = tool_call.get("id", "")

        logger.info("Tool call: %s(%s) [id=%s]", fn_name, fn_args, call_id)

        result_str = await handle_tool_call(fn_name, fn_args)

        results.append({
            "name": fn_name,
            "toolCallId": call_id,
            "result": result_str,
        })

    return JSONResponse(content={"results": results})


def _handle_assistant_request() -> JSONResponse:
    """Respond to assistant-request events (dynamic assistant config).

    This can be used to customise the assistant per-call (e.g. based on the
    caller's phone number).  For now we return an empty response so Vapi
    falls back to the default assistant configuration.
    """
    return JSONResponse(content={})

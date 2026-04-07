# Restaurant Phone Agent — Mia (מיה)

AI-powered phone agent for Israeli restaurants. Mia handles incoming calls in natural Hebrew, managing reservations, cancellations, and late-arrival coordination through **Vapi.ai** voice telephony with integrations for **Ontopo** and **Tabit** reservation systems.

## Architecture

```
Israeli Phone Number (Twilio)
        │
        ▼
  Vapi.ai Voice Agent
  (Deepgram STT → GPT-4o → ElevenLabs Hebrew TTS)
        │
        ▼  tool calls via HTTP
  FastAPI Webhook Server (/webhook)
        │
        ├── Ontopo Adapter  →  ontopo.com/api
        └── Tabit Adapter   →  reservations.tabit.cloud
```

**Call flow:** A customer dials the restaurant's number → Vapi answers with Mia's greeting → the LLM drives the conversation using the Hebrew system prompt → when Mia needs to check availability, book, or cancel, the LLM invokes a tool → Vapi sends the tool call to the webhook server → the server queries Ontopo/Tabit and returns the result → Mia communicates the outcome to the customer.

## Quick Start

### 1. Prerequisites

- Python 3.12+
- A [Vapi.ai](https://vapi.ai) account with API key
- An [ElevenLabs](https://elevenlabs.io) account (for Hebrew TTS voice)
- A [Twilio](https://twilio.com) account with an Israeli phone number (for production)

### 2. Install

```bash
git clone <this-repo>
cd restaurant-phone-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys and restaurant config
```

### 3. Start the Webhook Server

```bash
python -m src.main
```

The server starts on `http://0.0.0.0:8000`. For local development, expose it with ngrok:

```bash
ngrok http 8000
```

### 4. Create the Vapi Assistant

```bash
# Dry run — inspect the payload
python -m src.vapi_assistant --dry-run --server-url https://YOUR-NGROK-URL/webhook

# Create the assistant
python -m src.vapi_assistant --server-url https://YOUR-NGROK-URL/webhook
```

### 5. Attach a Phone Number

1. Import your Israeli Twilio number into Vapi (dashboard or API)
2. Assign the assistant ID to that phone number
3. Call the number — Mia answers

## Project Structure

```
config.py                       # Environment-based settings (Pydantic Settings)
src/
  main.py                       # FastAPI app with uvicorn
  webhook.py                    # Vapi webhook handler
  models.py                     # Pydantic models (Booking, Venue, etc.)
  reservation_router.py         # Dispatches tool calls to the correct adapter
  vapi_assistant.py             # Script to create/update the Vapi assistant
  adapters/
    base.py                     # Abstract ReservationAdapter interface
    ontopo.py                   # Ontopo API client (search, availability, booking URL)
    tabit.py                    # Tabit stub adapter (mock data, ready for real API)
  prompts/
    system_prompt.py            # Mia's Hebrew system prompt
  tools/
    definitions.py              # Vapi tool/function schemas
```

## Tools Available to Mia

| Tool | Description |
|------|-------------|
| `check_availability` | Query available time slots for a date/time/party size |
| `book_reservation` | Create a booking (returns confirmation or booking URL) |
| `find_reservation` | Look up existing reservation by customer name |
| `cancel_reservation` | Cancel a reservation by ID |
| `check_restaurant_load` | Get current pressure level (green/yellow/red) |
| `transfer_to_human` | Escalate call to a human agent |

## Reservation Systems

### Ontopo (fully integrated)

Uses the Ontopo web API at `ontopo.com/api`:
- Anonymous JWT authentication
- Venue search, availability checking, booking URL generation
- Supports all Israeli cities

**Limitation:** The public API does not support placing reservations directly — it generates a booking URL. For production, consider Ontopo's partner program or browser automation.

### Tabit (stub — ready for integration)

Tabit has no public developer API. The adapter provides the full interface with mock data. To integrate:
- Contact Tabit for API partnership
- Or reverse-engineer `reservations.tabit.cloud` network requests
- Replace the stub methods in `src/adapters/tabit.py`

## Configuration

All configuration is via environment variables (`.env` file). See `.env.example` for the full list.

Key settings:

| Variable | Description |
|----------|-------------|
| `VAPI_API_KEY` | Vapi dashboard API key |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice for Hebrew TTS |
| `RESERVATION_SYSTEM` | `ontopo` or `tabit` |
| `RESTAURANT_NAME` | Restaurant name (used in Mia's greeting) |
| `RESTAURANT_VENUE_ID` | Venue ID in the reservation system |
| `RESTAURANT_CITY` | City slug for Ontopo (e.g., `tel-aviv`) |

## Docker

```bash
docker compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook` | Vapi tool-call webhook |
| GET | `/health` | Health check |

## Voice Platform Notes

- **TTS:** ElevenLabs `eleven_multilingual_v2` with Hebrew voice. Format preprocessing is disabled (`inputPreprocessingEnabled: false`) to preserve Hebrew diacritics.
- **STT:** Deepgram Nova-2 with Hebrew language code (`he`).
- **LLM:** GPT-4o with temperature 0.3 for consistent, reliable responses.

If Hebrew quality is insufficient, consider switching to [Yappr](https://goyappr.com) (native Israeli platform) or [Retell AI](https://retellai.com) — the backend is platform-agnostic.

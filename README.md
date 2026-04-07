# Restaurant Phone Agent — Mia (מיה)

AI-powered phone agent for Israeli restaurants. Mia handles incoming calls in natural Hebrew, managing reservations, cancellations, and late-arrival coordination through **Vapi.ai** voice telephony with integrations for **Ontopo** and **Tabit** reservation systems.

Includes a **web dashboard** for managing multiple restaurants — add a restaurant through the UI and a Vapi assistant is created automatically.

## Architecture

```
                     ┌──────────────────────────────┐
                     │   Admin Dashboard (:8000)     │
                     │   Add / Edit / Delete         │
                     │   restaurants via web UI       │
                     └──────────┬───────────────────┘
                                │ saves to
                                ▼
                         SQLite Database
                     (data/restaurants.db)
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                      │
    Israeli Phone #1      Israeli Phone #2        Phone #N
          │                     │                      │
    Vapi Assistant #1     Vapi Assistant #2       Assistant #N
    (auto-created)        (auto-created)         (auto-created)
          │                     │                      │
          └─────────────────────┼──────────────────────┘
                                │ tool calls via HTTP
                                ▼
                     POST /webhook
                     (identifies restaurant by assistantId)
                                │
                     ┌──────────┴──────────┐
                     ▼                     ▼
               Ontopo Adapter        Tabit Adapter
               (ontopo.com/api)      (stub / future API)
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- A [Vapi.ai](https://vapi.ai) account with API key
- An [ElevenLabs](https://elevenlabs.io) account (for Hebrew TTS voice)

### 2. Install

```bash
git clone <this-repo>
cd restaurant-phone-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Vapi + ElevenLabs API keys
```

### 3. Run

```bash
python -m src.main
```

Open **http://localhost:8000** in your browser — the dashboard is ready.

### 4. Add a Restaurant

1. Click **"Add Restaurant"** in the dashboard
2. Fill in the restaurant name, reservation system (Ontopo/Tabit), venue ID, and city
3. Click **"Create Restaurant"** — a Vapi assistant is created automatically
4. Import an Israeli Twilio number into Vapi and assign the assistant
5. Customers call the number — Mia answers in Hebrew

## Dashboard

The web dashboard is served directly by FastAPI (no npm, no build step). It uses Tailwind CSS and HTMX for a modern, responsive UI.

**Features:**
- View all restaurants with status indicators
- Add new restaurants with automatic Vapi assistant provisioning
- Edit restaurant configuration (syncs changes to Vapi)
- Activate / deactivate restaurants
- Delete restaurants (also removes the Vapi assistant)
- View Vapi integration details and webhook URL

## Project Structure

```
config.py                       # Global settings (Vapi key, ElevenLabs, DB URL)
src/
  main.py                       # FastAPI app with uvicorn
  dashboard.py                  # Dashboard web UI + REST API for CRUD
  webhook.py                    # Vapi webhook handler (multi-restaurant)
  database.py                   # SQLAlchemy ORM (Restaurant model, SQLite)
  models.py                     # Pydantic models (Booking, Venue, etc.)
  reservation_router.py         # Per-restaurant adapter factory + tool dispatch
  vapi_service.py               # Vapi API client (create/update/delete assistant)
  vapi_assistant.py             # CLI wrapper for vapi_service
  adapters/
    base.py                     # Abstract ReservationAdapter interface
    ontopo.py                   # Ontopo API client (search, availability, booking)
    tabit.py                    # Tabit stub adapter (mock data, ready for real API)
  prompts/
    system_prompt.py            # Mia's Hebrew system prompt
  tools/
    definitions.py              # Vapi tool/function schemas
  templates/
    base.html                   # Base layout (Tailwind + HTMX)
    restaurant_list.html        # Restaurant list page
    restaurant_form.html        # Add/edit form
    restaurant_detail.html      # Detail view
data/
  restaurants.db                # SQLite database (auto-created)
```

## Configuration

Only global settings go in `.env` — per-restaurant config lives in the database.

| Variable | Description |
|----------|-------------|
| `VAPI_API_KEY` | Vapi dashboard API key |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID for Hebrew TTS |
| `SERVER_URL` | Public URL where Vapi can reach the webhook |
| `WEBHOOK_PORT` | Server port (default: 8000) |
| `DATABASE_URL` | SQLite path (default: `sqlite:///data/restaurants.db`) |

## Multi-Restaurant Webhook Routing

When a customer calls, Vapi sends tool calls to `POST /webhook` with the `assistantId` in the payload. The server:

1. Extracts `assistantId` from `message.call.assistantId`
2. Looks up the restaurant in SQLite by `vapi_assistant_id`
3. Creates the correct adapter (Ontopo or Tabit) for that restaurant
4. Routes the tool call and returns the result to Vapi

## Tools Available to Mia

| Tool | Description |
|------|-------------|
| `check_availability` | Query available time slots for a date/time/party size |
| `book_reservation` | Create a booking (returns confirmation or booking URL) |
| `find_reservation` | Look up existing reservation by customer name |
| `cancel_reservation` | Cancel a reservation by ID |
| `check_restaurant_load` | Get current pressure level (green/yellow/red) |
| `transfer_to_human` | Escalate call to a human agent |

## Docker

```bash
docker compose up --build
```

The database persists in a Docker volume (`db-data`).

## Tests

```bash
python -m pytest tests/ -v                        # 16 pass, 2 skip
ONTOPO_LIVE_TESTS=1 python -m pytest tests/ -v    # includes live Ontopo API
```

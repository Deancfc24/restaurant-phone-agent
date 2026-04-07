"""Restaurant Phone Agent — FastAPI application entry-point.

Serves both the admin dashboard and the Vapi webhook.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from config import settings
from src.database import init_db
from src.reservation_router import shutdown_all_adapters
from src.webhook import router as webhook_router
from src.dashboard import router as dashboard_router


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger = logging.getLogger(__name__)

    # Ensure the data directory exists for SQLite
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    init_db()
    logger.info("Database initialised at %s", settings.database_url)
    logger.info(
        "Dashboard running at http://%s:%s",
        settings.webhook_host,
        settings.webhook_port,
    )
    yield
    logger.info("Shutting down — closing adapters")
    await shutdown_all_adapters()


app = FastAPI(
    title="Restaurant Phone Agent",
    description="Dashboard + webhook server for Mia, the AI restaurant phone hostess",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def main() -> None:
    _configure_logging()
    uvicorn.run(
        "src.main:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=True,
    )


if __name__ == "__main__":
    main()

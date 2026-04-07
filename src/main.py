"""Restaurant Phone Agent — FastAPI application entry-point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from config import settings
from src.reservation_router import shutdown_adapter
from src.webhook import router as webhook_router


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
    logger.info(
        "Starting Restaurant Phone Agent for '%s' (system=%s)",
        settings.restaurant_name,
        settings.reservation_system,
    )
    yield
    logger.info("Shutting down — closing adapter")
    await shutdown_adapter()


app = FastAPI(
    title="Restaurant Phone Agent",
    description="Webhook server for Mia, the AI restaurant phone hostess",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "restaurant": settings.restaurant_name,
        "system": settings.reservation_system,
    }


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

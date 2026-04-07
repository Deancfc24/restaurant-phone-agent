"""SQLAlchemy database layer — Restaurant ORM model and session management."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, create_engine, event
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from config import settings


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: uuid.uuid4().hex
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    venue_id: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="tel-aviv")
    reservation_system: Mapped[str] = mapped_column(String, default="ontopo")
    phone_number: Mapped[str] = mapped_column(String, default="")

    vapi_assistant_id: Mapped[Optional[str]] = mapped_column(String, default=None)
    vapi_phone_number_id: Mapped[Optional[str]] = mapped_column(String, default=None)

    tabit_organization_id: Mapped[str] = mapped_column(String, default="")
    tabit_api_key: Mapped[str] = mapped_column(String, default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "venue_id": self.venue_id,
            "city": self.city,
            "reservation_system": self.reservation_system,
            "phone_number": self.phone_number,
            "vapi_assistant_id": self.vapi_assistant_id,
            "vapi_phone_number_id": self.vapi_phone_number_id,
            "tabit_organization_id": self.tabit_organization_id,
            "tabit_api_key": self.tabit_api_key,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


engine = create_engine(settings.database_url, echo=False)

# Enable WAL mode for SQLite (better concurrent read performance)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Yield a DB session (for use as a FastAPI dependency)."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def get_restaurant_by_assistant_id(assistant_id: str) -> Restaurant | None:
    """Look up a restaurant by its Vapi assistant ID."""
    with SessionLocal() as db:
        return (
            db.query(Restaurant)
            .filter(Restaurant.vapi_assistant_id == assistant_id, Restaurant.is_active == True)
            .first()
        )

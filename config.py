from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -- Vapi --
    vapi_api_key: str = ""
    vapi_phone_number_id: str = ""

    # -- ElevenLabs --
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # -- Webhook server --
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""

    # -- Restaurant --
    reservation_system: str = "ontopo"
    restaurant_name: str = "My Restaurant"
    restaurant_venue_id: str = ""
    restaurant_city: str = "tel-aviv"

    # -- Tabit --
    tabit_organization_id: str = ""
    tabit_api_key: str = ""

    # -- Logging --
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

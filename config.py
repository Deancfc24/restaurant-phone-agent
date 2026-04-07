from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # -- Vapi (global account key) --
    vapi_api_key: str = ""

    # -- ElevenLabs (global) --
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # -- Server --
    server_url: str = "http://localhost:8000"
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""

    # -- Database --
    database_url: str = "sqlite:///data/restaurants.db"

    # -- Logging --
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

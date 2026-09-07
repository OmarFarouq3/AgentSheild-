"""Frontend-only settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LAYER_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = LAYER_ROOT.parent
SECRETS_DIR = Path(os.getenv("SECRETS_DIR", PROJECT_ROOT / "secrets"))
ENV_FILE = Path(os.getenv("FRONTEND_ENV_FILE", SECRETS_DIR / "frontend_layer.env"))


class FrontendSettings(BaseSettings):
    """Settings used by the Chainlit frontend."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )

    fastapi_chat_url: str = Field(default="http://localhost:8000/chat", alias="FASTAPI_CHAT_URL")
    fastapi_security_suite_url: str = Field(
        default="http://localhost:8000/security/attack-suite",
        alias="FASTAPI_SECURITY_SUITE_URL",
    )
    request_timeout_seconds: float = Field(default=35.0, alias="REQUEST_TIMEOUT_SECONDS")
    security_suite_timeout_seconds: float = Field(default=600.0, alias="SECURITY_SUITE_TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_frontend_settings() -> FrontendSettings:
    """Return cached frontend settings."""

    return FrontendSettings()  # type: ignore[call-arg]

"""Agent settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LAYER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = LAYER_ROOT.parent
SECRETS_DIR = Path(os.getenv("SECRETS_DIR", PROJECT_ROOT / "secrets"))
ENV_FILE = Path(os.getenv("AGENT_ENV_FILE", SECRETS_DIR / "agent_layer.env"))


class AgentSettings(BaseSettings):
    """Runtime settings for model calls, API routes, MCP endpoints, and databases."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )

    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    chat_model: str = Field(default="qwen3.5:4b", alias="CHAT_MODEL")
    ollama_context_length: int = Field(default=4096, ge=1024, alias="OLLAMA_CONTEXT_LENGTH")
    ollama_temperature: float = Field(default=0.0, ge=0.0, le=2.0, alias="OLLAMA_TEMPERATURE")
    ollama_seed: int = Field(default=42, ge=0, alias="OLLAMA_SEED")
    ollama_think: bool = Field(default=False, alias="OLLAMA_THINK")
    ollama_keep_alive: str = Field(default="10m", alias="OLLAMA_KEEP_ALIVE")
    security_mode: Literal["normal", "defended"] = Field(default="defended", alias="SECURITY_MODE")
    security_harness_api_enabled: bool = Field(default=True, alias="SECURITY_HARNESS_API_ENABLED")
    security_results_dir: Path = Field(
        default=PROJECT_ROOT.parent / "results" / "security_runs",
        alias="SECURITY_RESULTS_DIR",
    )
    git_commit: str = Field(default="unknown", alias="GIT_COMMIT")
    git_branch: str = Field(default="unknown", alias="GIT_BRANCH")
    postgres_url: str = Field(
        default="postgresql://techpulse:techpulse@localhost:5432/techpulse",
        alias="POSTGRES_URL",
    )
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")

    faq_mcp_url: str = Field(default="http://localhost:8001/mcp", alias="FAQ_MCP_URL")
    request_timeout_seconds: float = Field(default=120.0, alias="REQUEST_TIMEOUT_SECONDS")
    default_top_k: int = Field(default=5, alias="DEFAULT_TOP_K")
    max_top_k: int = Field(default=5, alias="MAX_TOP_K")


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    """Return cached agent settings."""

    return AgentSettings()  # type: ignore[call-arg]

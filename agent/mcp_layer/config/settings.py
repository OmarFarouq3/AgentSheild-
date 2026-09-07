"""MCP layer settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LAYER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = LAYER_ROOT.parent
SECRETS_DIR = Path(os.getenv("SECRETS_DIR", PROJECT_ROOT / "secrets"))
ENV_FILE = Path(os.getenv("MCP_ENV_FILE", SECRETS_DIR / "mcp_layer.env"))
DEFAULT_GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


class McpSettings(BaseSettings):
    """Settings used by MCP servers, MCP clients, and retrieval services."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )

    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    embedding_model: str = Field(default="nomic-embed-text:v1.5", alias="EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=768, gt=0, alias="EMBEDDING_DIMENSION")
    embedding_timeout_seconds: float = Field(default=60.0, gt=0, alias="EMBEDDING_TIMEOUT_SECONDS")
    reset_collection: bool = Field(default=False, alias="RESET_COLLECTION")

    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="faq_chunks", alias="QDRANT_COLLECTION")

    github_mcp_url: str = Field(default=DEFAULT_GITHUB_MCP_URL, alias="GITHUB_MCP_URL")
    fetch_mcp_url: str | None = Field(default=None, alias="FETCH_MCP_URL")
    fetch_mcp_command: str = Field(default="python", alias="FETCH_MCP_COMMAND")
    fetch_mcp_args: str = Field(default="-m mcp_server_fetch", alias="FETCH_MCP_ARGS")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    fetch_timeout_seconds: float = Field(default=10.0, alias="FETCH_TIMEOUT_SECONDS")

    default_top_k: int = Field(default=5, alias="DEFAULT_TOP_K")
    max_top_k: int = Field(default=5, alias="MAX_TOP_K")
    min_retrieval_score: float = Field(default=0.0, alias="MIN_RETRIEVAL_SCORE")


@lru_cache(maxsize=1)
def get_mcp_settings() -> McpSettings:
    """Return cached MCP layer settings."""

    return McpSettings()  # type: ignore[call-arg]

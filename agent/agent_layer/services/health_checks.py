"""Agent dependency and readiness checks."""

from __future__ import annotations

import asyncio

import asyncpg
import httpx

from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings

logger = get_logger(__name__)
HEALTH_CHECK_TIMEOUT_SECONDS = 0.5
MODEL_HEALTH_CHECK_TIMEOUT_SECONDS = 2.0


async def check_agent_ready() -> bool:
    """Verify that Ollama is reachable and the configured chat model is installed."""

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=MODEL_HEALTH_CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()

        models = payload.get("models", []) if isinstance(payload, dict) else []
        installed_models = {
            str(value).strip()
            for model in models
            if isinstance(model, dict)
            for value in (model.get("name"), model.get("model"))
            if value
        }
        model_ready = settings.chat_model in installed_models
        if not model_ready:
            logger.debug(
                "Configured Ollama model is not installed",
                extra={"chat_model": settings.chat_model},
            )
        return model_ready
    except Exception as exc:
        logger.debug(
            "Ollama health check failed",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        return False


async def check_qdrant() -> bool:
    """Actively ping Qdrant."""

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections")
            response.raise_for_status()
        return True
    except Exception as exc:
        logger.debug(
            "Qdrant health check failed",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        return False


async def check_postgres() -> bool:
    """Actively ping PostgreSQL."""

    try:
        settings = get_settings()
        conn = await asyncpg.connect(dsn=settings.postgres_url, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
        try:
            value = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
            return value == 1
        finally:
            await conn.close()
    except Exception as exc:
        logger.debug(
            "Postgres health check failed",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        return False

"""Health check route."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter

from agent_layer.api.api_schemas import HealthResponse
from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings
from agent_layer.services.health_checks import check_agent_ready, check_postgres, check_qdrant

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Return process readiness for Docker health checks."""

    return {"status": "ready"}


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check backend and agent dependencies."""

    started = time.perf_counter()
    qdrant_ok, postgres_ok, agent_ok = await asyncio.gather(
        check_qdrant(),
        check_postgres(),
        check_agent_ready(),
    )
    status = "healthy" if qdrant_ok and postgres_ok and agent_ok else "degraded"
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.debug(
        "Health check",
        extra={
            "qdrant_ok": qdrant_ok,
            "postgres_ok": postgres_ok,
            "agent": agent_ok,
            "latency_ms": latency_ms,
        },
    )
    return HealthResponse(
        status=status,
        qdrant=qdrant_ok,
        postgres=postgres_ok,
        agent=agent_ok,
        version=get_settings().app_version,
    )

"""Health routes for the TechPulse FAQ MCP server."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_layer.config.logging import get_logger
from mcp_layer.services.retrieval_tool import ensure_retrieval_tool_ready

logger = get_logger(__name__)


async def health(_request) -> JSONResponse:
    """Return FAQ MCP health for Docker and orchestration checks."""

    try:
        ensure_retrieval_tool_ready()
        return JSONResponse({"status": "healthy", "qdrant": True})
    except Exception as exc:
        logger.warning(
            "FAQ MCP health degraded",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        return JSONResponse({"status": "degraded", "qdrant": False}, status_code=200)


async def ready(_request) -> JSONResponse:
    """Return process readiness for Docker health checks."""

    return JSONResponse({"status": "ready"})


routes = [
    Route("/ready", endpoint=ready, methods=["GET"]),
    Route("/health", endpoint=health, methods=["GET"]),
]

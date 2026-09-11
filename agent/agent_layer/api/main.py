"""FastAPI app construction for the AgentShield agent layer."""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings
from agent_layer.api.middleware import request_id_middleware
from agent_layer.api.routes import chat_routes, health_routes, root_routes, security_routes
from agent_layer.services.postgres_tool import close_pool, get_pool
from agent_layer.services.runtime import close_model_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifecycle hook."""

    settings = get_settings()
    logger.info("AgentShield API starting", extra={"version": settings.app_version})
    await get_pool()
    try:
        yield
    finally:
        await close_model_client()
        await close_pool()
        logger.info("AgentShield API stopped")


app = FastAPI(
    title="AgentShield AI Agent API",
    version="1.0.0",
    lifespan=lifespan,
)
app.middleware("http")(request_id_middleware)
app.include_router(root_routes.router)
app.include_router(health_routes.router)
app.include_router(chat_routes.router)
app.include_router(security_routes.router)

# The repo-level dashboard is optional in agent-only Docker deployments.
try:
    from frontend.server import install_dashboard
except ModuleNotFoundError as exc:
    if exc.name not in {"frontend", "frontend.server"}:
        raise
else:
    install_dashboard(app)


@app.exception_handler(Exception)
async def generic_exception_handler(_request, exc: Exception) -> JSONResponse:
    """Return safe generic errors for unhandled exceptions."""

    logger.error(
        "Unhandled application error",
        extra={"error_type": type(exc).__name__, "error_message": str(exc)},
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

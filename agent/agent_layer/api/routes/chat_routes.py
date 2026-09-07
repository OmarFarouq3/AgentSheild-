"""Chat route that delegates work to the agent runtime."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from agent_layer.api.api_schemas import ChatRequest, ChatResponse
from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings
from agent_layer.services.runtime import run_agent

router = APIRouter(tags=["chat"])
logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run the TechPulse agent and return the final answer."""

    logger.info(
        "Incoming request",
        extra={
            "query_length": len(request.query),
            "session_id": request.session_id,
        },
    )

    try:
        settings = get_settings()
        result = await asyncio.wait_for(
            run_agent(
                query=request.query,
                session_id=request.session_id,
                max_tool_calls=request.max_tool_calls,
            ),
            timeout=settings.request_timeout_seconds,
        )
        return ChatResponse.model_validate(result.model_dump())
    except asyncio.TimeoutError as exc:
        logger.error(
            "Agent timeout",
            extra={
                "error_type": type(exc).__name__,
                "error_message": f"Agent exceeded {settings.request_timeout_seconds:g} seconds",
            },
        )
        raise HTTPException(status_code=504, detail="Agent exceeded the request timeout.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent request failed")
        raise HTTPException(status_code=503, detail="The TechPulse agent is temporarily unavailable.") from exc

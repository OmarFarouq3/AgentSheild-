"""Root/status route."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["info"])


@router.get("/")
async def root() -> dict[str, str]:
    """Return a simple API running message."""

    return {"message": "TechPulse AI Agent API is running. Use POST /chat or GET /health."}


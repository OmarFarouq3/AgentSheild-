"""Controlled endpoints for the School of Cyber Defense demonstration."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from agent_layer.api.api_schemas import AdaptiveSuiteRequest, SecuritySuiteRequest
from agent_layer.config.settings import get_settings
from agent_layer.services.adaptive_harness import run_adaptive_suite
from agent_layer.services.adaptive_generator import STRATEGIES
from agent_layer.services.adaptive_scope import validate_model_endpoint
from agent_layer.services.security_harness import attack_catalog, run_before_after_suite

router = APIRouter(prefix="/security", tags=["security-harness"])
_suite_lock = asyncio.Lock()


def _require_harness_api() -> None:
    if not get_settings().security_harness_api_enabled:
        raise HTTPException(status_code=404, detail="Security harness API is disabled.")


@router.get("/attack-cases")
async def list_attack_cases() -> dict[str, object]:
    """List the fixed, synthetic attack cases without running the model."""

    _require_harness_api()
    return {"attack_cases": attack_catalog()}


@router.post("/attack-suite")
async def run_attack_suite(request: SecuritySuiteRequest) -> dict[str, object]:
    """Run the same attack suite before and after the local defences are enabled."""

    _require_harness_api()
    if _suite_lock.locked():
        raise HTTPException(status_code=409, detail="A security suite is already running in this worker.")
    async with _suite_lock:
        return await run_before_after_suite(max_tool_calls=request.max_tool_calls)


@router.get("/adaptive-cases")
async def list_adaptive_cases() -> dict[str, object]:
    _require_harness_api()
    return {"categories": STRATEGIES, "defaults": AdaptiveSuiteRequest().model_dump(),
            "comparison": "Every candidate runs unchanged against normal and defended in fresh sessions."}


@router.post("/adaptive-suite")
async def run_adaptive_campaign(request: AdaptiveSuiteRequest) -> dict[str, object]:
    _require_harness_api()
    try:
        validate_model_endpoint(get_settings().ollama_base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if _suite_lock.locked():
        raise HTTPException(status_code=409, detail="A security suite is already running in this worker.")
    async with _suite_lock:
        return await run_adaptive_suite(request)

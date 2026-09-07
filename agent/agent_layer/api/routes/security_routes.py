"""Controlled endpoints for the School of Cyber Defense demonstration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent_layer.api.api_schemas import SecuritySuiteRequest
from agent_layer.config.settings import get_settings
from agent_layer.services.security_harness import attack_catalog, run_before_after_suite

router = APIRouter(prefix="/security", tags=["security-harness"])


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
    return await run_before_after_suite(max_tool_calls=request.max_tool_calls)

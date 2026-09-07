"""Synchronous bridge to the real TechPulse runtime (not the demo adapter)."""

import asyncio
from collections import deque
from pathlib import Path
import sys

# The target uses top-level agent_layer and mcp_layer imports.
AGENT_ROOT = Path(__file__).resolve().parents[1] / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


def get_system_canary():
    from agent_layer.services.security_controls import SYSTEM_PROMPT_CANARY
    return SYSTEM_PROMPT_CANARY


def normalize_result(result):
    """Include dispatched calls, excluding guard denials and budget-skipped calls."""
    tools_called = []
    pending = deque()
    for event in result.transcript:
        if event.get("event") == "model_response":
            pending = deque(event["tool_calls"])
        elif event.get("event") == "tool_result":
            if not pending:
                raise ValueError("Tool result has no matching model call.")
            call = pending.popleft()
            if call["name"] != event["tool_name"]:
                raise ValueError("Tool trace order does not match model calls.")
            output = event["output"]
            if output.get("blocked"):
                continue
            if not output.get("ok"):
                raise RuntimeError(
                    f"Tool {call['name']} failed; this run cannot be graded."
                )
            if not isinstance(call["name"], str) or not isinstance(call["arguments"], dict):
                raise ValueError("Invalid tool trace.")
            tools_called.append({"name": call["name"], "arguments": dict(call["arguments"])})
    return {"response": result.answer, "tools_called": tools_called}


async def _run_agent(prompt, security_mode):
    from agent_layer.config.settings import get_settings
    from agent_layer.services.postgres_tool import close_pool
    from agent_layer.services.runtime import close_model_client, run_agent as run_target

    try:
        result = await asyncio.wait_for(
            run_target(
                query=prompt, session_id=None, max_tool_calls=5,
                security_mode=security_mode,
            ),
            timeout=get_settings().request_timeout_seconds,
        )
        return normalize_result(result)
    finally:
        try:
            await close_model_client()
        finally:
            await close_pool()


def run_agent(prompt, *, security_mode=None):
    """Run one fresh session. Errors propagate rather than becoming BLOCKED."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if security_mode not in (None, "baseline", "defended"):
        raise ValueError("security_mode must be baseline or defended")
    return asyncio.run(_run_agent(prompt, security_mode))

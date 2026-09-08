"""Synchronous bridge to the real TechPulse runtime (not the demo adapter)."""

import asyncio
from collections import deque
from pathlib import Path
import sys
from urllib.parse import urlparse

from evaluation.isolation import isolated_dispatch


class AgentExecutionError(RuntimeError):
    """Execution failure retaining all evidence available from the runtime."""

    def __init__(self, message, agent_result):
        super().__init__(message)
        self.agent_result = agent_result

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
    intercepted = []
    errors = []
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
                errors.append(f"Tool {call['name']} failed: {output.get('error_type', 'error')}: "
                              f"{output.get('error_message', '')}")
                continue
            if not isinstance(call["name"], str) or not isinstance(call["arguments"], dict):
                raise ValueError("Invalid tool trace.")
            captured = {"name": call["name"], "arguments": dict(call["arguments"])}
            if isinstance(output.get("result"), dict) and output["result"].get("evaluation_intercepted"):
                intercepted.append(captured)
            else:
                tools_called.append(captured)
    evidence = {"response": result.answer, "tools_called": tools_called,
                "intercepted_tool_calls": intercepted, "transcript": result.transcript,
                "latency_ms": getattr(result, "latency_ms", None)}
    if errors:
        raise AgentExecutionError("; ".join(errors), evidence)
    return evidence


def get_test_context(security_mode=None):
    """Inspect the actual posture and synthetic markers without running tools."""
    from agent_layer.config.settings import get_settings
    from agent_layer.services.security_controls import CONFIDENTIAL_CANARY
    from agent_layer.utils.prompts import system_instructions_for_mode

    mode = security_mode or get_settings().security_mode
    canary = get_system_canary()
    return {
        "security_mode": mode,
        "system_canary": canary,
        "confidential_canary": CONFIDENTIAL_CANARY,
        "system_canary_available": canary in system_instructions_for_mode(mode),
        "model": get_settings().chat_model,
    }


async def _run_agent(prompt, security_mode):
    from agent_layer.config.settings import get_settings
    from agent_layer.services.postgres_tool import close_pool
    from agent_layer.services.runtime import close_model_client, run_agent as run_target
    from agent_layer.services import dispatcher

    # This pipeline is explicitly local; never send prompts to a remote model.
    model_url = urlparse(get_settings().ollama_base_url)
    if model_url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Day 2 evaluation requires a loopback Ollama endpoint.")

    try:
        with isolated_dispatch(dispatcher):
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
    if security_mode not in (None, "normal", "defended"):
        raise ValueError("security_mode must be normal or defended")
    return asyncio.run(_run_agent(prompt, security_mode))

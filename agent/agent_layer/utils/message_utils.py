"""Helpers for normalizing native Ollama chat response dictionaries."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def extract_assistant_message(response: Any) -> dict[str, Any]:
    """Return a safe assistant message from a native ``/api/chat`` response."""

    if not isinstance(response, Mapping):
        return {}
    message = response.get("message")
    if not isinstance(message, Mapping):
        return {}
    return dict(message)


def extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    """Return well-shaped tool calls and ignore malformed model output."""

    raw_calls = extract_assistant_message(response).get("tool_calls", [])
    if not isinstance(raw_calls, list):
        return []

    calls: list[dict[str, Any]] = []
    for raw_call in raw_calls:
        if not isinstance(raw_call, Mapping):
            continue
        function = raw_call.get("function")
        if not isinstance(function, Mapping):
            continue
        if not str(function.get("name") or "").strip():
            continue
        calls.append(dict(raw_call))
    return calls


def parse_tool_call(tool_call: Any) -> tuple[str, dict[str, Any]]:
    """Extract a tool name and tolerate object or JSON-string arguments."""

    if not isinstance(tool_call, Mapping):
        return "", {}
    function = tool_call.get("function")
    if not isinstance(function, Mapping):
        return "", {}

    name = str(function.get("name") or "").strip()
    raw_arguments = function.get("arguments", {})
    if isinstance(raw_arguments, Mapping):
        return name, dict(raw_arguments)
    if isinstance(raw_arguments, str):
        try:
            parsed_arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return name, {}
        if isinstance(parsed_arguments, Mapping):
            return name, dict(parsed_arguments)
    return name, {}


def extract_final_answer(response: Any) -> str:
    """Extract final assistant text with a safe fallback."""

    content = extract_assistant_message(response).get("content", "")
    return content.strip() if isinstance(content, str) else ""

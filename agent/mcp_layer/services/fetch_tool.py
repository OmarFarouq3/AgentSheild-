"""Fetch tool for live public URL content.

The SRS-compliant path calls an external Fetch MCP server. By default this uses
the official/reference stdio Fetch server package (`python -m mcp_server_fetch`).
"""

from __future__ import annotations

import asyncio
import re
import shlex
import time
from typing import Any
from urllib.parse import urlparse

from mcp_layer.config.logging import get_logger
from mcp_layer.config.settings import get_mcp_settings
from mcp_layer.services.client import call_mcp_tool, call_stdio_mcp_tool

logger = get_logger(__name__)


def _validate_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http(s) URL.")
    return cleaned


def _to_plain_text(value: Any, max_characters: int) -> str:
    """Normalize Fetch MCP output into plain text for the API response."""
    if isinstance(value, dict):
        text = str(value.get("content") or value.get("text") or value)
    else:
        text = str(value or "")

    # The official Fetch server returns markdown. Keep the content readable but
    # remove HTML tags and the most visible markdown wrappers for the SRS plain
    # text response contract.
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#|~]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_characters]


async def _call_fetch_mcp(cleaned_url: str, safe_max: int) -> Any:
    """Call Fetch MCP using HTTP if configured, otherwise stdio."""
    settings = get_mcp_settings()
    preferred_tool_names = ("fetch", "fetch_url", "fetch_public_url")
    arguments = {"url": cleaned_url, "max_length": safe_max}

    if settings.fetch_mcp_url:
        return await call_mcp_tool(
            settings.fetch_mcp_url,
            preferred_tool_names=preferred_tool_names,
            arguments=arguments,
        )

    return await call_stdio_mcp_tool(
        settings.fetch_mcp_command,
        args=shlex.split(settings.fetch_mcp_args),
        preferred_tool_names=preferred_tool_names,
        arguments=arguments,
    )


async def fetch_public_url(url: str, max_characters: int = 6000) -> dict[str, Any]:
    """Fetch a public URL through the external Fetch MCP server."""
    settings = get_mcp_settings()
    cleaned_url = _validate_url(url)
    try:
        requested_max = int(max_characters)
    except (TypeError, ValueError):
        requested_max = 6000
    safe_max = max(500, min(requested_max, 12000))
    started = time.perf_counter()

    try:
        result = await asyncio.wait_for(
            _call_fetch_mcp(cleaned_url, safe_max),
            timeout=settings.fetch_timeout_seconds,
        )
        text = _to_plain_text(result, safe_max)
        latency_ms = int((time.perf_counter() - started) * 1000)

        logger.info(
            "Fetch MCP call completed",
            extra={
                "tool_name": "fetch_public_url",
                "input_summary": {"url_host": urlparse(cleaned_url).netloc},
                "result_count": 1 if text else 0,
                "latency_ms": latency_ms,
            },
        )
        return {"source": cleaned_url, "content": text, "content_length": len(text)}
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.error(
            "Fetch tool error",
            extra={
                "tool_name": "fetch_public_url",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "latency_ms": latency_ms,
            },
        )
        raise

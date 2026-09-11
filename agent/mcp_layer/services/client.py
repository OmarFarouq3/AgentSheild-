"""Small helpers for calling MCP servers.

The custom FAQ server is called through Streamable HTTP. External tools may use
Streamable HTTP or stdio, depending on how the reference MCP server is exposed.
"""

from __future__ import annotations

import json
from builtins import BaseExceptionGroup
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any, Iterable

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from mcp_layer.config.logging import get_logger

logger = get_logger(__name__)


def _flatten_exception_messages(exc: BaseException) -> list[str]:
    """Return useful leaf exception messages from regular or grouped errors."""

    if isinstance(exc, BaseExceptionGroup):
        messages: list[str] = []
        for child in exc.exceptions:
            messages.extend(_flatten_exception_messages(child))
        return messages

    message = str(exc).strip()
    if message:
        return [f"{type(exc).__name__}: {message}"]
    return [type(exc).__name__]


def _mcp_failure_message(server_url: str, exc: BaseException) -> str:
    messages = _flatten_exception_messages(exc)
    detail = "; ".join(dict.fromkeys(messages))
    if not detail:
        detail = type(exc).__name__

    hint = ""
    if "api.githubcopilot.com/mcp" in server_url:
        hint = (
            " Check GITHUB_TOKEN authentication and access to GitHub's hosted MCP "
            "endpoint."
        )

    return f"MCP call to {server_url} failed: {detail}.{hint}"


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "dict"):
        dumped = value.dict(exclude_none=True)
        if isinstance(dumped, dict):
            return dumped
    return {}


def parse_mcp_result(tool_result: Any) -> Any:
    """Extract structured JSON-compatible data from an MCP CallToolResult."""
    if getattr(tool_result, "isError", False) or getattr(tool_result, "is_error", False):
        raise RuntimeError(f"MCP tool returned an error: {tool_result!r}")

    structured_content = (
        getattr(tool_result, "structured_content", None)
        or getattr(tool_result, "structuredContent", None)
    )
    if structured_content is not None:
        return structured_content

    texts: list[str] = []
    for content_item in getattr(tool_result, "content", []) or []:
        if isinstance(content_item, dict):
            text = content_item.get("text")
        else:
            text = getattr(content_item, "text", None)
        if text:
            texts.append(text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue

    if texts:
        return "\n".join(texts)

    return None


def _select_preferred_tool(available_tools: Any, preferred_tool_names: Iterable[str]) -> str:
    """Return the first available tool name that matches the preferred list."""
    preferred = list(preferred_tool_names)
    by_name = {getattr(tool, "name", ""): tool for tool in available_tools}

    for tool_name in preferred:
        if tool_name in by_name:
            return tool_name

    raise RuntimeError(
        "None of the preferred MCP tools were found. "
        f"preferred={preferred} available={sorted(by_name)}"
    )


@asynccontextmanager
async def _streamable_http_transport(
    server_url: str,
    headers: dict[str, str] | None = None,
) -> AsyncIterator[Any]:
    """Open a Streamable HTTP MCP transport with optional request headers."""

    if headers:
        async with httpx.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(server_url, http_client=http_client) as transport:
                yield transport
        return

    async with streamable_http_client(server_url) as transport:
        yield transport


async def call_mcp_tool(
    server_url: str,
    preferred_tool_names: Iterable[str],
    arguments: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Any:
    """Call a Streamable HTTP MCP tool by preferred name.

    headers is used for authenticated remote MCP servers such as GitHub's
    official hosted MCP endpoint. Header values are never logged.
    """

    try:
        async with _streamable_http_transport(
            server_url,
            headers=headers,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                available_tools = getattr(tools_response, "tools", [])
                tool_name = _select_preferred_tool(available_tools, preferred_tool_names)

                logger.info(
                    "Calling MCP tool",
                    extra={"tool_name": tool_name, "server_url": server_url},
                )
                result = await session.call_tool(tool_name, arguments=arguments)
                return parse_mcp_result(result)
    except Exception as exc:
        raise RuntimeError(_mcp_failure_message(server_url, exc)) from exc


async def call_stdio_mcp_tool(
    command: str,
    args: list[str],
    preferred_tool_names: Iterable[str],
    arguments: dict[str, Any],
) -> Any:
    """Launch a stdio MCP server and call a tool by preferred name."""

    server_params = StdioServerParameters(command=command, args=args)

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            available_tools = getattr(tools_response, "tools", [])
            tool_name = _select_preferred_tool(available_tools, preferred_tool_names)

            logger.info(
                "Calling stdio MCP tool",
                extra={"tool_name": tool_name, "command": command},
            )
            result = await session.call_tool(tool_name, arguments=arguments)
            return parse_mcp_result(result)


async def list_mcp_tools_for_model(
    server_url: str,
    headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Discover MCP tools and convert them to the local model's function schema."""
    async with _streamable_http_transport(
        server_url,
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            model_tools: list[dict[str, Any]] = []
            for tool in getattr(tools_response, "tools", []) or []:
                input_schema = (
                    getattr(tool, "inputSchema", None)
                    or getattr(tool, "input_schema", None)
                    or {"type": "object", "properties": {}}
                )
                model_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": getattr(tool, "name", ""),
                            "description": getattr(tool, "description", None) or "",
                            "parameters": _to_plain_dict(input_schema),
                        },
                    }
                )
            return model_tools

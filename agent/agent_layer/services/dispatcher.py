"""Safe dispatch for model-selected tool calls."""

from __future__ import annotations

from typing import Any

from agent_layer.config.logging import get_logger, get_request_id
from agent_layer.config.settings import get_settings
from agent_layer.services.postgres_tool import query_saved_repositories
from agent_layer.services.security_controls import (
    SENSITIVE_TOOL_NAME,
    UNTRUSTED_DOCUMENT_TOOL_NAME,
    assert_tool_allowed,
)
from agent_layer.services.security_documents import read_confidential_document, read_partner_brief
from mcp_layer.services.client import call_mcp_tool
from mcp_layer.services.fetch_tool import fetch_public_url
from mcp_layer.services.github_tool import (
    github_get_repo_metadata,
    github_list_topics,
    github_search_repositories,
)
from mcp_layer.services.retrieval_tool import RETRIEVAL_TOOL_NAME, run_retrieval_tool

logger = get_logger(__name__)


def _postgres_missing_parameter_result(intent: str, parameter: str) -> dict[str, Any]:
    """Return a model-readable validation result for incomplete saved-repo calls."""

    return {
        "intent": intent,
        "rows": [],
        "rows_returned": 0,
        "validation_error": (
            f"Missing required parameter params.{parameter} for {intent}. "
            "Use github_mcp_tool for live public GitHub repository metadata, or provide "
            "the exact saved owner/repo name when querying saved TechPulse records."
        ),
    }


def _validated_postgres_arguments(arguments: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    """Validate saved repository query arguments before opening a DB connection."""

    intent = str(arguments.get("intent", "")).strip()
    raw_params = arguments.get("params") or {}
    params = raw_params if isinstance(raw_params, dict) else {}

    required_by_intent = {
        "repositories_by_tag": "tag",
        "repository_details": "name",
        "repositories_by_author": "username",
    }
    required_parameter = required_by_intent.get(intent)
    if required_parameter and not str(params.get(required_parameter, "")).strip():
        return intent, params, _postgres_missing_parameter_result(intent, required_parameter)

    return intent, params, None


def _int_argument(value: Any, default: int) -> int:
    """Coerce model-provided numeric arguments without letting bad values escape dispatch."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch a model-selected tool call through approved Python callables."""

    settings = get_settings()
    assert_tool_allowed(tool_name)

    if tool_name == UNTRUSTED_DOCUMENT_TOOL_NAME:
        return read_partner_brief()

    if tool_name == SENSITIVE_TOOL_NAME:
        return read_confidential_document(document_id=str(arguments.get("document_id", "")))

    if tool_name == "github_mcp_tool":
        operation = str(arguments.get("operation", "")).strip()
        if operation == "search_repositories":
            return await github_search_repositories(
                query=str(arguments.get("query", "")),
                limit=_int_argument(arguments.get("limit"), 5),
            )
        if operation == "get_repo_metadata":
            return await github_get_repo_metadata(full_name=str(arguments.get("full_name", "")))
        if operation == "list_topics":
            return await github_list_topics(full_name=str(arguments.get("full_name", "")))
        raise ValueError("Unsupported GitHub operation.")

    if tool_name == "github_search_repositories":
        return await github_search_repositories(
            query=str(arguments.get("query", "")),
            limit=_int_argument(arguments.get("limit"), 5),
        )

    if tool_name == "github_get_repo_metadata":
        return await github_get_repo_metadata(full_name=str(arguments.get("full_name", "")))

    if tool_name == "github_list_topics":
        return await github_list_topics(full_name=str(arguments.get("full_name", "")))

    if tool_name == "fetch_mcp_tool":
        return await fetch_public_url(
            url=str(arguments.get("url", "")),
            max_characters=_int_argument(arguments.get("max_characters"), 6000),
        )

    if tool_name == "fetch_public_url":
        return await fetch_public_url(
            url=str(arguments.get("url", "")),
            max_characters=_int_argument(arguments.get("max_characters"), 6000),
        )

    if tool_name == RETRIEVAL_TOOL_NAME:
        request_id = get_request_id()
        faq_arguments = {
            "query": str(arguments.get("query", "")),
            "top_k": arguments.get("top_k"),
            "request_id": request_id,
        }
        try:
            return await call_mcp_tool(
                settings.faq_mcp_url,
                preferred_tool_names=(RETRIEVAL_TOOL_NAME,),
                arguments=faq_arguments,
            )
        except Exception as exc:
            logger.warning(
                "FAQ MCP call failed; using local retrieval fallback",
                extra={
                    "tool_name": RETRIEVAL_TOOL_NAME,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            return run_retrieval_tool(
                query=faq_arguments["query"],
                top_k=faq_arguments["top_k"],
            )

    if tool_name == "query_saved_repositories":
        intent, params, validation_error = _validated_postgres_arguments(arguments)
        if validation_error is not None:
            return validation_error
        return await query_saved_repositories(intent=intent, params=params)

    raise RuntimeError(f"Unknown tool requested by model: {tool_name}")

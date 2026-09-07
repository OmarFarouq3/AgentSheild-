"""GitHub repository tools backed by the official GitHub MCP server.

The SRS requires GitHub access through an external MCP server. These functions
therefore call GitHub's hosted Streamable HTTP MCP endpoint by default instead
of using a direct REST fallback.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from mcp_layer.config.logging import get_logger
from mcp_layer.config.settings import get_mcp_settings
from mcp_layer.services.client import call_mcp_tool

logger = get_logger(__name__)

OFFICIAL_GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"
GITHUB_SEARCH_TOOL_NAMES = (
    "search_repositories",
    "search_repos",
    "github_search_repositories",
    "searchRepositories",
)
GITHUB_METADATA_TOOL_NAMES = (
    "get_repository",
    "get_repo_metadata",
    "github_get_repo_metadata",
    "getRepository",
)


def _github_mcp_url() -> str:
    """Return the configured GitHub MCP URL or fail clearly."""

    settings = get_mcp_settings()
    server_url = (settings.github_mcp_url or "").strip()
    if not server_url:
        raise RuntimeError(
            "GITHUB_MCP_URL is required. Use GitHub's official remote MCP URL: "
            f"{OFFICIAL_GITHUB_MCP_URL}"
        )
    return server_url


def _github_mcp_headers() -> dict[str, str]:
    """Return optional auth headers for the GitHub MCP server."""

    settings = get_mcp_settings()
    token = (settings.github_token or "").strip()
    if not token:
        return {}

    return {"Authorization": f"Bearer {token}"}


def _split_repo_full_name(full_name: str) -> tuple[str, str]:
    """Validate and split an owner/repo repository name."""

    cleaned = full_name.strip().strip("/")
    parts = cleaned.split("/")
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise ValueError("full_name must look like 'owner/repo'.")
    return parts[0].strip(), parts[1].strip()


def _extract_topics(repository_result: Any) -> list[str]:
    """Best-effort extraction of repository topics from MCP metadata."""

    if isinstance(repository_result, dict):
        direct_topics = repository_result.get("topics")
        if isinstance(direct_topics, list):
            return [str(topic) for topic in direct_topics]

        repository = repository_result.get("repository")
        if isinstance(repository, dict) and isinstance(repository.get("topics"), list):
            return [str(topic) for topic in repository["topics"]]

    return []


def _is_missing_preferred_tool_error(exc: BaseException) -> bool:
    """Return True when MCP discovery found no matching preferred tool."""

    return "None of the preferred MCP tools were found" in str(exc)


def _repository_owner_name(candidate: dict[str, Any]) -> tuple[str, str] | None:
    """Extract owner/repo from common GitHub MCP repository shapes."""

    for key in ("full_name", "fullName", "nameWithOwner", "name_with_owner"):
        value = candidate.get(key)
        if isinstance(value, str) and "/" in value:
            owner, repo = _split_repo_full_name(value)
            return owner, repo

    owner_value = candidate.get("owner")
    if isinstance(owner_value, dict):
        owner = owner_value.get("login") or owner_value.get("name")
    else:
        owner = owner_value
    repo = candidate.get("name")
    if isinstance(owner, str) and isinstance(repo, str) and owner.strip() and repo.strip():
        return owner.strip(), repo.strip()

    for key in ("html_url", "url"):
        value = candidate.get(key)
        if not isinstance(value, str):
            continue
        parsed = urlparse(value)
        if parsed.netloc.lower() != "github.com":
            continue
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) >= 2:
            return parts[0], parts[1]

    return None


def _iter_repository_candidates(value: Any) -> list[dict[str, Any]]:
    """Collect repository-like dictionaries from varied MCP search responses."""

    candidates: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            candidates.extend(_iter_repository_candidates(item))
        return candidates

    if not isinstance(value, dict):
        return candidates

    if _repository_owner_name(value) is not None:
        candidates.append(value)

    for nested in value.values():
        if isinstance(nested, (dict, list)):
            candidates.extend(_iter_repository_candidates(nested))

    return candidates


def _find_exact_repository(search_result: Any, owner: str, repo: str) -> Any:
    """Return the exact owner/repo match from a GitHub search payload."""

    expected = (owner.lower(), repo.lower())
    for candidate in _iter_repository_candidates(search_result):
        candidate_owner_name = _repository_owner_name(candidate)
        if candidate_owner_name and tuple(part.lower() for part in candidate_owner_name) == expected:
            return candidate
    return search_result


async def _github_search_repositories_raw(
    query: str,
    limit: int,
    *,
    minimal_output: bool = True,
) -> Any:
    return await call_mcp_tool(
        _github_mcp_url(),
        preferred_tool_names=GITHUB_SEARCH_TOOL_NAMES,
        arguments={
            "query": query,
            "sort": "stars",
            "order": "desc",
            "perPage": limit,
            "minimal_output": minimal_output,
        },
        headers=_github_mcp_headers(),
    )


async def github_search_repositories(query: str, limit: int = 5) -> dict[str, Any]:
    """Search public GitHub repositories by keyword through the GitHub MCP server."""

    cleaned = query.strip()
    if not cleaned:
        raise ValueError("GitHub search query cannot be empty.")

    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = 5
    safe_limit = max(1, min(requested_limit, 10))
    started = time.perf_counter()

    result = await _github_search_repositories_raw(cleaned, safe_limit)

    response_size = len(str(result))
    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "GitHub MCP search completed",
        extra={
            "tool_name": "github_search_repositories",
            "query": cleaned,
            "response_size": response_size,
            "latency_ms": latency_ms,
        },
    )
    return {"source": "github_mcp", "results": result}


async def github_get_repo_metadata(full_name: str) -> dict[str, Any]:
    """Retrieve repository metadata through the GitHub MCP server."""

    owner, repo = _split_repo_full_name(full_name)
    started = time.perf_counter()

    used_search_fallback = False
    try:
        result = await call_mcp_tool(
            _github_mcp_url(),
            preferred_tool_names=GITHUB_METADATA_TOOL_NAMES,
            arguments={"owner": owner, "repo": repo},
            headers=_github_mcp_headers(),
        )
    except RuntimeError as exc:
        if not _is_missing_preferred_tool_error(exc):
            raise

        search_query = f"repo:{owner}/{repo}"
        search_result = await _github_search_repositories_raw(
            search_query,
            5,
            minimal_output=False,
        )
        result = _find_exact_repository(search_result, owner, repo)
        used_search_fallback = True

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "GitHub MCP metadata completed",
        extra={
            "tool_name": "github_get_repo_metadata",
            "query": f"{owner}/{repo}",
            "response_size": len(str(result)),
            "retrieval_method": "search_repositories_fallback" if used_search_fallback else "metadata_tool",
            "latency_ms": latency_ms,
        },
    )
    return {"source": "github_mcp", "repository": result}


async def github_list_topics(full_name: str) -> dict[str, Any]:
    """List public GitHub topics for a repository using MCP metadata."""

    started = time.perf_counter()
    owner, repo = _split_repo_full_name(full_name)
    metadata = await github_get_repo_metadata(f"{owner}/{repo}")
    repository_result = metadata.get("repository")
    topics = _extract_topics(repository_result)

    result = {
        "source": metadata.get("source", "github_mcp"),
        "repository": f"{owner}/{repo}",
        "topics": topics,
        "metadata": repository_result,
    }

    logger.info(
        "GitHub MCP topics list completed",
        extra={
            "tool_name": "github_list_topics",
            "query": f"{owner}/{repo}",
            "result_count": len(topics),
            "response_size": len(str(result)),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return result

"""Tool call result tracking, source extraction, and lightweight run telemetry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp_layer.services.retrieval_tool import RETRIEVAL_TOOL_NAME


def result_count_for(tool_name: str, result: Any) -> int:
    """Best-effort count of records returned by a tool result."""

    if not isinstance(result, dict):
        return 1 if result else 0
    if tool_name == "query_saved_repositories":
        return int(result.get("rows_returned", 0))
    if tool_name == RETRIEVAL_TOOL_NAME:
        return int(result.get("chunks_found", 0))
    if "results" in result and isinstance(result["results"], list):
        return len(result["results"])
    if "content" in result:
        return 1 if result.get("content") else 0
    if "repository" in result:
        return 1
    return 1


def collect_sources(tool_name: str, result: Any) -> list[str]:
    """Collect source labels for the chat response."""

    if not isinstance(result, dict):
        return []

    if tool_name == RETRIEVAL_TOOL_NAME:
        return [str(source) for source in result.get("sources", [])]

    if tool_name in {"fetch_public_url", "fetch_mcp_tool"}:
        return [str(result.get("source"))] if result.get("source") else []

    if tool_name == "query_saved_repositories":
        return [f"postgres:{result.get('intent', 'query')}"]

    if tool_name.startswith("github_") or tool_name == "github_mcp_tool":
        sources: list[str] = []
        if isinstance(result.get("results"), list):
            for repo in result["results"]:
                if isinstance(repo, dict) and repo.get("html_url"):
                    sources.append(repo["html_url"])
        repository = result.get("repository")
        if isinstance(repository, dict) and repository.get("html_url"):
            sources.append(repository["html_url"])
        return sources or ["github"]

    return []


@dataclass
class AgentRunTracker:
    """Mutable per-run counters for the agent runtime."""

    tool_calls_made: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    total_tool_calls: int = 0

    def record_tool_call(self, tool_name: str) -> None:
        """Record that the model selected a tool."""

        self.total_tool_calls += 1
        self.tool_calls_made.append(tool_name)

    def record_tool_result(self, tool_name: str, result: Any) -> int:
        """Record successful tool result metadata and return the observed count."""

        for source in collect_sources(tool_name, result):
            if source and source not in self.sources:
                self.sources.append(source)
        return result_count_for(tool_name, result)

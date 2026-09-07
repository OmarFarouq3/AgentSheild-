"""Agent graph wrapper and tool schema registry."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from agent_layer.utils.tool_schemas import AgentResult
from agent_layer.utils.tool_schemas import model_tools


@dataclass(frozen=True)
class AgentGraph:
    """Container for tool schemas and execution routing."""

    tools: list[dict[str, Any]]


class AgentGraphState(TypedDict):
    """State passed through the LangGraph workflow."""

    query: str
    session_id: str | None
    max_tool_calls: int
    result: AgentResult | None


def build_agent_graph() -> AgentGraph:
    """Build the agent graph/tool registry."""

    return AgentGraph(tools=model_tools())


async def run_agent_workflow(
    query: str,
    session_id: str | None,
    max_tool_calls: int,
    runner: Callable[[str, str | None, int], Awaitable[AgentResult]],
) -> AgentResult:
    """Run the agent through a LangGraph workflow.

    LangGraph is installed in the Docker image through requirements.txt. The
    fallback keeps local import checks usable before dependencies are installed.
    """

    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return await runner(query, session_id, max_tool_calls)

    async def assistant_node(state: AgentGraphState) -> dict[str, AgentResult]:
        result = await runner(
            state["query"],
            state.get("session_id"),
            state["max_tool_calls"],
        )
        return {"result": result}

    workflow = StateGraph(AgentGraphState)
    workflow.add_node("assistant", assistant_node)
    workflow.set_entry_point("assistant")
    workflow.add_edge("assistant", END)
    compiled = workflow.compile()
    final_state = await compiled.ainvoke(
        {
            "query": query,
            "session_id": session_id,
            "max_tool_calls": max_tool_calls,
            "result": None,
        }
    )
    result = final_state.get("result")
    if result is None:
        raise RuntimeError("Agent workflow did not produce a result.")
    return result

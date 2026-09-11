"""Main agent runtime and guarded local-model/tool loop."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from agent_layer.config.logging import get_logger
from agent_layer.config.settings import get_settings
from agent_layer.services import dispatcher
from agent_layer.services.graph import build_agent_graph, run_agent_workflow
from agent_layer.services.security_controls import (
    SecurityMode,
    active_security_mode,
    guard_tool_call,
    guard_retrieved_result,
    guard_user_input,
    redact_sensitive_output,
    security_mode_scope,
)
from agent_layer.services.tracking import AgentRunTracker
from agent_layer.utils.message_utils import extract_final_answer, extract_tool_calls, parse_tool_call
from agent_layer.utils.prompts import system_instructions_for_mode
from agent_layer.utils.tool_schemas import AgentResult
from mcp_layer.services.retrieval_tool import RETRIEVAL_TOOL_NAME

logger = get_logger(__name__)
session_histories: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY_MESSAGES = 8
_model_client: httpx.AsyncClient | None = None


def get_model_client() -> httpx.AsyncClient:
    """Return a reusable HTTP client for the local Ollama service."""

    global _model_client
    settings = get_settings()
    if _model_client is None:
        _model_client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    return _model_client


async def close_model_client() -> None:
    """Close the reusable Ollama HTTP client during application shutdown."""

    global _model_client
    if _model_client is not None:
        await _model_client.aclose()
        _model_client = None


def get_history(session_id: str | None) -> list[dict[str, str]]:
    """Return recent session history if a session id was supplied."""

    if not session_id:
        return []
    return session_histories.get(session_id, [])[-MAX_HISTORY_MESSAGES:]


def save_history(session_id: str | None, user_query: str, answer: str) -> None:
    """Persist minimal in-memory history for future multi-turn support."""

    if not session_id:
        return
    session_histories.setdefault(session_id, []).extend(
        [
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": answer},
        ]
    )
    session_histories[session_id] = session_histories[session_id][-MAX_HISTORY_MESSAGES:]


def build_model_input(query: str, history: list[dict[str, str]]) -> list[Any]:
    """Build native Ollama messages from system instructions and recent history."""

    input_messages: list[Any] = [
        {"role": "system", "content": system_instructions_for_mode(active_security_mode())}
    ]
    input_messages.extend(
        {"role": item["role"], "content": item["content"]}
        for item in history
        if item.get("content", "").strip()
    )
    input_messages.append({"role": "user", "content": query})
    return input_messages


def should_search_faq(query: str) -> bool:
    """Detect questions that are specifically about the bundled AgentShield FAQ domain.

    Small local models can answer these from the wording alone instead of selecting
    the retrieval tool.  Preflighting only distinctive product/architecture terms
    keeps ordinary greetings, live GitHub requests, and unrelated questions unchanged.
    """

    normalized = " ".join(query.casefold().split())
    # Adaptive prompts often mention the product while carrying an attack
    # instruction; those must continue through the red-team path unchanged.
    if any(signal in normalized for signal in (
        "ignore ", "reveal ", "system prompt", "confidential", "canary", "bypass ",
        "read_confidential", "read_partner_brief", "override ",
    )):
        return False
    faq_signals = (
        "agentshield", "faq", "qdrant", "fastapi endpoint", "health endpoint",
        "postgres query", "repository tables", "structured repository", "docker compose",
        "containerized", "logging requirements", "logging requirement",
    )
    return any(signal in normalized for signal in faq_signals)


async def call_model(input_messages: list[Any], force_final_answer: bool = False) -> dict[str, Any]:
    """Call Ollama's native non-streaming chat endpoint."""

    settings = get_settings()
    client = get_model_client()
    graph = build_agent_graph()
    payload: dict[str, Any] = {
        "model": settings.chat_model,
        "messages": input_messages,
        "stream": False,
        "think": settings.ollama_think,
        "keep_alive": settings.ollama_keep_alive,
        "options": {
            "num_ctx": settings.ollama_context_length,
            "temperature": settings.ollama_temperature,
            "seed": settings.ollama_seed,
        },
    }
    if not force_final_answer:
        payload["tools"] = graph.tools

    try:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=payload,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            error_payload = exc.response.json()
            if isinstance(error_payload, dict):
                detail = str(error_payload.get("error") or "").strip()
        except ValueError:
            detail = ""
        suffix = f" Ollama said: {detail}" if detail else ""
        raise RuntimeError(
            f"Ollama chat request failed with HTTP {exc.response.status_code}.{suffix} "
            f"Ensure the configured model is installed with "
            f"'ollama pull {settings.chat_model}'."
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {settings.ollama_base_url}. "
            "Start Ollama and verify OLLAMA_BASE_URL."
        ) from exc
    try:
        response_data = response.json()
    except ValueError as exc:
        raise RuntimeError("Ollama returned an invalid JSON response.") from exc
    if not isinstance(response_data, dict) or not isinstance(response_data.get("message"), dict):
        raise RuntimeError("Ollama response did not contain an assistant message.")
    return response_data


async def _run_tool_loop(query: str, session_id: str | None, max_tool_calls: int) -> AgentResult:
    """Run the local model agent loop with guarded tool calls."""

    history = get_history(session_id)
    tracker = AgentRunTracker()
    started = time.perf_counter()
    transcript: list[dict[str, Any]] = [
        {"event": "run_started", "security_mode": active_security_mode()},
        {"event": "user_input", "content": query},
    ]
    input_decision = guard_user_input(query)
    if input_decision.blocked:
        transcript.append(
            {
                "event": "guard_blocked",
                "control": input_decision.control,
                "reason": input_decision.reason,
            }
        )
        answer = (
            "I can’t help fabricate or present an unverified cybersecurity claim as fact. "
            "I can help verify an advisory using authoritative sources."
            if input_decision.control == "security_claim_guard"
            else "I can’t help override instructions or expose protected information."
        )
        return AgentResult(
            answer=answer,
            sources=[],
            tool_calls_made=[],
            latency_ms=int((time.perf_counter() - started) * 1000),
            transcript=transcript,
        )

    input_messages = build_model_input(query, history)
    response = None
    preflighted_faq = False

    # The FAQ is a first-party knowledge source, so make its use deterministic for
    # clearly AgentShield-specific questions. This prevents a small local model from
    # confidently answering from its prior knowledge without consulting the FAQ.
    if should_search_faq(query) and max_tool_calls > 0:
        faq_tool_call = {
            "function": {
                "name": RETRIEVAL_TOOL_NAME,
                "arguments": {"query": query, "top_k": 3},
            }
        }
        tracker.record_tool_call(RETRIEVAL_TOOL_NAME)
        transcript.append({
            "event": "tool_selected",
            "tool_name": RETRIEVAL_TOOL_NAME,
            "arguments": {"query": query, "top_k": 3},
            "selection": "faq_intent_preflight",
        })
        try:
            faq_result = await dispatcher.execute_tool(RETRIEVAL_TOOL_NAME, {"query": query, "top_k": 3})
            faq_result, retrieval_decision = guard_retrieved_result(faq_result)
            if retrieval_decision.blocked:
                transcript.append({"event": "guard_blocked", "control": retrieval_decision.control,
                                   "reason": retrieval_decision.reason, "tool_name": RETRIEVAL_TOOL_NAME})
            tracker.record_tool_result(RETRIEVAL_TOOL_NAME, faq_result)
            faq_output = {"ok": True, "result": faq_result}
        except Exception as exc:
            logger.error("FAQ preflight failed", extra={"error_type": type(exc).__name__, "error_message": str(exc)})
            faq_output = {"ok": False, "error_type": type(exc).__name__, "error_message": str(exc)}
        transcript.append({"event": "tool_result", "tool_name": RETRIEVAL_TOOL_NAME, "output": faq_output})
        input_messages.extend([
            {"role": "assistant", "content": "", "tool_calls": [faq_tool_call]},
            {"role": "tool", "tool_name": RETRIEVAL_TOOL_NAME,
             "content": json.dumps(faq_output, ensure_ascii=False, default=str)},
        ])
        if tracker.total_tool_calls >= max_tool_calls:
            response = await call_model(input_messages, force_final_answer=True)
            preflighted_faq = True

    while tracker.total_tool_calls < max_tool_calls and not (preflighted_faq and response is not None):
        response = await call_model(input_messages)
        tool_calls = extract_tool_calls(response)
        transcript.append(
            {
                "event": "model_response",
                "content": extract_final_answer(response),
                "tool_calls": [
                    {"name": parse_tool_call(call)[0], "arguments": parse_tool_call(call)[1]}
                    for call in tool_calls
                ],
            }
        )
        if not tool_calls:
            break

        remaining_calls = max_tool_calls - tracker.total_tool_calls
        selected_calls = tool_calls[:remaining_calls]
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": extract_final_answer(response),
            "tool_calls": selected_calls,
        }
        input_messages.append(assistant_message)

        for tool_call in selected_calls:
            tool_name, arguments = parse_tool_call(tool_call)
            if not tool_name:
                continue

            tracker.record_tool_call(tool_name)
            logger.info(
                "Tool selected",
                extra={
                    "tool_name": tool_name,
                    "input_summary": {
                        "argument_keys": sorted(arguments.keys()),
                        "argument_count": len(arguments),
                    },
                },
            )

            tool_started = time.perf_counter()
            tool_decision = guard_tool_call(tool_name, arguments)
            if tool_decision.blocked:
                output = {
                    "ok": False,
                    "blocked": True,
                    "control": tool_decision.control,
                    "reason": tool_decision.reason,
                }
            else:
                try:
                    result = await dispatcher.execute_tool(tool_name, arguments)
                    result, retrieval_decision = guard_retrieved_result(result)
                    if retrieval_decision.blocked:
                        transcript.append({"event": "guard_blocked", "control": retrieval_decision.control,
                                           "reason": retrieval_decision.reason, "tool_name": tool_name})
                    latency_ms = int((time.perf_counter() - tool_started) * 1000)
                    count = tracker.record_tool_result(tool_name, result)
                    logger.info(
                        "Tool response",
                        extra={
                            "tool_name": tool_name,
                            "result_count": count,
                            "latency_ms": latency_ms,
                        },
                    )
                    output = {"ok": True, "result": result}
                except Exception as exc:
                    latency_ms = int((time.perf_counter() - tool_started) * 1000)
                    logger.error(
                        "Tool error",
                        extra={
                            "tool_name": tool_name,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "latency_ms": latency_ms,
                        },
                    )
                    output = {
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }

            transcript.append(
                {
                    "event": "tool_result",
                    "tool_name": tool_name,
                    "output": output,
                }
            )

            input_messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": json.dumps(output, ensure_ascii=False, default=str),
                }
            )

    if response is None:
        raise RuntimeError("Agent did not produce a response.")

    if tracker.total_tool_calls >= max_tool_calls and not preflighted_faq:
        input_messages.append(
            {
                "role": "user",
                "content": (
                    "You reached the maximum tool call limit. Give the best final "
                    "answer using the tool results already available."
                ),
            }
        )
        response = await call_model(input_messages, force_final_answer=True)

    answer = extract_final_answer(response)
    if not answer:
        answer = "I could not produce a grounded answer from the available tool results."
    answer, output_decision = redact_sensitive_output(answer)
    if output_decision.blocked:
        transcript.append(
            {
                "event": "guard_blocked",
                "control": output_decision.control,
                "reason": output_decision.reason,
            }
        )
    transcript.append({"event": "final_answer", "content": answer})

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "Agent response",
        extra={
            "total_tool_calls": tracker.total_tool_calls,
            "total_latency_ms": latency_ms,
        },
    )
    return AgentResult(
        answer=answer,
        sources=tracker.sources,
        tool_calls_made=tracker.tool_calls_made,
        latency_ms=latency_ms,
        transcript=transcript,
    )


async def run_agent(
    query: str,
    session_id: str | None,
    max_tool_calls: int,
    security_mode: SecurityMode | None = None,
) -> AgentResult:
    """Run the AgentShield agent through the configured LangGraph workflow."""

    with security_mode_scope(security_mode):
        result = await run_agent_workflow(query, session_id, max_tool_calls, _run_tool_loop)
    save_history(session_id, query, result.answer)
    return result

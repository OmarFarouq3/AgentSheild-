"""Optional Chainlit frontend for the TechPulse FastAPI agent.

Run after FastAPI is up:
    chainlit run frontend_layer/app/chainlit_app.py -w --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import uuid

import chainlit as cl
import httpx

from frontend_layer.app.config.logging import get_logger
from frontend_layer.app.config.settings import get_frontend_settings

logger = get_logger(__name__)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("session_id", str(uuid.uuid4()))
    await cl.Message(
        content=(
            "Hello! Ask me about tech repositories, URLs, or the TechPulse FAQ. "
            "For the School of Cyber Defense demo, send `/run-security-suite`."
        )
    ).send()


async def _run_security_suite() -> str:
    """Call the controlled before/after suite and format its presentation summary."""

    settings = get_frontend_settings()
    async with httpx.AsyncClient(timeout=settings.security_suite_timeout_seconds) as http_client:
        response = await http_client.post(
            settings.fastapi_security_suite_url,
            json={"max_tool_calls": 3},
        )
        response.raise_for_status()
        report = response.json()

    normal = report["normal"]
    defended = report["defended"]
    rows = [
        "| Posture | Blocked | Partial | Succeeded | Success rate | Residual risk |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| Normal | {normal['blocked']} | {normal['partial']} | "
            f"{normal['succeeded']} | {normal['attack_success_rate_percent']}% | "
            f"{normal['residual_risk_score_percent']}% |"
        ),
        (
            f"| Defended | {defended['blocked']} | {defended['partial']} | "
            f"{defended['succeeded']} | {defended['attack_success_rate_percent']}% | "
            f"{defended['residual_risk_score_percent']}% |"
        ),
    ]
    return (
        "## Security-harness result\n\n"
        + "\n".join(rows)
        + f"\n\nSuccess-rate drop: **{report['success_rate_drop_percentage_points']} percentage points**."
        + f" Residual-risk drop: **{report['residual_risk_drop_percentage_points']} percentage points**."
        + "\n\nTranscript evidence for each attack is retained in the API response.\n\n"
        + f"Residual gap: {report['residual_gap_note']}"
    )


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_text = (message.content or "").strip()
    if not user_text:
        await cl.Message(content="Please type a question first.").send()
        return

    thinking = cl.Message(content="Thinking...")
    await thinking.send()

    try:
        if user_text == "/run-security-suite":
            thinking.content = await _run_security_suite()
            await thinking.update()
            return

        settings = get_frontend_settings()
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as http_client:
            response = await http_client.post(
                settings.fastapi_chat_url,
                json={
                    "query": user_text,
                    "session_id": cl.user_session.get("session_id"),
                    "max_tool_calls": 5,
                },
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("answer") or "I could not produce an answer."
        sources = data.get("sources") or []
        if sources:
            answer += "\n\nSources used:\n" + "\n".join(f"- {source}" for source in sources[:8])
        thinking.content = answer
        await thinking.update()

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else None
        logger.warning("FastAPI returned an error", extra={"status_code": status_code})
        if status_code == 422:
            thinking.content = "Please enter a valid question and try again."
        elif status_code == 504:
            thinking.content = "The agent took too long to answer. Please try a narrower question."
        else:
            thinking.content = "The TechPulse agent is temporarily unavailable."
        await thinking.update()

    except httpx.RequestError as exc:
        logger.error(
            "Could not connect to FastAPI",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        thinking.content = "Could not connect to the TechPulse API."
        await thinking.update()

    except Exception:
        logger.exception("Unexpected Chainlit error")
        thinking.content = "Something went wrong while processing your question."
        await thinking.update()

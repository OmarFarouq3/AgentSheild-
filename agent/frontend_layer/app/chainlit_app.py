"""Optional Chainlit frontend for the AgentShield FastAPI agent.

Run after FastAPI is up:
    chainlit run frontend_layer/app/chainlit_app.py -w --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import uuid

import chainlit as cl
import httpx

from frontend_layer.app.config.logging import get_logger
from frontend_layer.app.config.settings import get_frontend_settings
from frontend_layer.app.security_reports import (
    ADAPTIVE_COMMAND,
    adaptive_round_messages,
    adaptive_summary,
    inert_json,
    parse_adaptive_command,
    report_bytes,
    validate_adaptive_report,
)

logger = get_logger(__name__)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("session_id", str(uuid.uuid4()))
    settings = get_frontend_settings()
    await cl.Message(
        content=(
            "Hello! Ask me about tech repositories, URLs, or the AgentShield FAQ. "
            "For the School of Cyber Defense demo:\n\n"
            "- `/run-security-suite` runs the fixed before/after checks.\n"
            f"- `/run-adaptive-suite` runs up to {settings.adaptive_suite_rounds} adaptive rounds "
            f"with the {settings.adaptive_suite_generator} generator against both postures.\n"
            "- `/run-adaptive-suite 6 model` sets 1–12 rounds and uses the local attack model. "
            "Use `policy` for the feedback-driven policy generator.\n\n"
            "Adaptive reports show attack lineage, generator fallbacks, scored outcomes, coverage, "
            "and target/tool evidence, with a full JSON download. A campaign can take several minutes."
        )
    ).send()


async def _run_security_suite() -> tuple[str, dict[str, object]]:
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
    summary = (
        "## Security-harness result\n\n"
        + "\n".join(rows)
        + f"\n\nSuccess-rate drop: **{report['success_rate_drop_percentage_points']} percentage points**."
        + f" Residual-risk drop: **{report['residual_risk_drop_percentage_points']} percentage points**."
        + "\n\nThe full report and transcript evidence are attached as JSON.\n\n"
        + "Residual gap:\n\n" + inert_json(report["residual_gap_note"])
    )
    return summary, report


async def _run_adaptive_suite(request: dict[str, object]) -> dict[str, object]:
    """Wait for the synchronous backend report without fabricating live progress."""

    settings = get_frontend_settings()
    async with httpx.AsyncClient(timeout=settings.adaptive_suite_timeout_seconds) as http_client:
        response = await http_client.post(settings.fastapi_adaptive_suite_url, json=request)
        response.raise_for_status()
        return validate_adaptive_report(response.json())


def _report_file(report: dict[str, object], *, adaptive: bool) -> cl.File:
    """Use a fixed filename; never use attacker-controlled strings as a file path."""

    return cl.File(
        name="adaptive-security-report.json" if adaptive else "security-report.json",
        content=report_bytes(report),
        display="inline",
        mime="application/json",
    )


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_text = (message.content or "").strip()
    if not user_text:
        await cl.Message(content="Please type a question first.").send()
        return

    command = user_text.split()[0]
    adaptive = command == ADAPTIVE_COMMAND
    suite = adaptive or user_text == "/run-security-suite"
    request = None
    if adaptive:
        settings = get_frontend_settings()
        try:
            request = parse_adaptive_command(
                user_text,
                default_rounds=settings.adaptive_suite_rounds,
                default_generator=settings.adaptive_suite_generator,
            )
        except ValueError as exc:
            await cl.Message(content=str(exc)).send()
            return
    if suite and cl.user_session.get("security_suite_running"):
        await cl.Message(content="A security suite is already running in this chat. Wait for its report before starting another.").send()
        return
    if suite:
        cl.user_session.set("security_suite_running", True)
    progress = "Thinking..."
    if request is not None:
        progress = (
            f"Running up to {request['rounds']} adaptive rounds with the {request['generator']} generator, "
            "testing each candidate against undefended and defended agents. "
            "Each target attempt has a 60-second limit and at most 3 tool calls. "
            "Waiting for the backend report; round evidence becomes available when this request completes."
        )
    elif suite:
        progress = "Running the fixed security suite against both postures. Waiting for the backend report..."
    thinking = cl.Message(content=progress)

    try:
        await thinking.send()
        if user_text == "/run-security-suite":
            thinking.content, report = await _run_security_suite()
            thinking.elements = [_report_file(report, adaptive=False)]
            await thinking.update()
            return
        if adaptive and request is not None:
            report = await _run_adaptive_suite(request)
            thinking.content = adaptive_summary(report)
            thinking.elements = [_report_file(report, adaptive=True)]
            await thinking.update()
            for evidence in adaptive_round_messages(report):
                await cl.Message(content=evidence).send()
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
        if suite and status_code in {404, 403}:
            thinking.content = "The security harness endpoint is unavailable or disabled. Check the backend harness setting and frontend suite URL. No report was received."
        elif suite and status_code in {409, 429}:
            thinking.content = "The security harness is busy or at its run limit. No new report was received; wait for the current campaign to finish before retrying."
        elif suite and status_code == 422:
            thinking.content = "The API rejected the suite settings. Check that frontend and backend support the same adaptive limits. No report was received."
        elif suite and status_code == 504:
            thinking.content = "The suite request timed out. Completion is unknown; inspect backend logs and saved campaign artifacts before retrying."
        elif suite:
            thinking.content = "The security suite API returned an error. No report was received; inspect backend logs and saved campaign artifacts before retrying."
        elif status_code == 422:
            thinking.content = "Please enter a valid question and try again."
        elif status_code == 504:
            thinking.content = "The agent took too long to answer. Please try a narrower question."
        else:
            thinking.content = "The AgentShield agent is temporarily unavailable."
        await thinking.update()

    except httpx.TimeoutException:
        thinking.content = (
            "The frontend timed out waiting for the security report. The backend may still be running; "
            "inspect backend logs and saved campaign artifacts before retrying. No result is available in this chat."
            if suite else "The agent took too long to answer. Please try a narrower question."
        )
        await thinking.update()

    except httpx.RequestError as exc:
        logger.error(
            "Could not connect to FastAPI",
            extra={"error_type": type(exc).__name__, "error_message": str(exc)},
        )
        thinking.content = (
            "The connection to the security API failed. Completion is unknown; inspect backend logs and saved campaign artifacts before retrying."
            if suite else "Could not connect to the AgentShield API."
        )
        await thinking.update()

    except Exception:
        logger.exception("Unexpected Chainlit error")
        thinking.content = (
            "The security report could not be retrieved or displayed. No complete report is available in this chat; "
            "inspect the backend campaign artifacts and logs."
            if suite else "Something went wrong while processing your question."
        )
        await thinking.update()
    finally:
        if suite:
            cl.user_session.set("security_suite_running", False)

"""Pure, inert presentation helpers for reviewer-facing security evidence.

Generated attacks and target transcripts are untrusted content. Keep every
free-text field inside a JSON code block whose fence cannot occur in its body.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


ADAPTIVE_COMMAND = "/run-adaptive-suite"
ADAPTIVE_USAGE = "Use `/run-adaptive-suite [rounds: 1-12] [model|policy]`."
_OUTCOMES = {
    "blocked": "Blocked",
    "partial": "Partial",
    "succeeded": "Succeeded",
    "not_exercised": "Not exercised",
    "error": "Error",
}
_GENERATORS = {"model": "Model", "policy": "Policy", "policy_fallback": "Policy fallback"}


def parse_adaptive_command(
    command: str, *, default_rounds: int = 4, default_generator: str = "model"
) -> dict[str, Any]:
    """Parse a small, bounded command without forwarding arbitrary API fields."""

    parts = command.split()
    if not parts or parts[0] != ADAPTIVE_COMMAND or len(parts) > 3:
        raise ValueError(ADAPTIVE_USAGE)
    rounds, generator = default_rounds, default_generator
    if len(parts) >= 2:
        if parts[1] in {"model", "policy"} and len(parts) == 2:
            generator = parts[1]
        elif re.fullmatch(r"[0-9]{1,2}", parts[1]):
            rounds = int(parts[1])
        else:
            raise ValueError(ADAPTIVE_USAGE)
    if len(parts) == 3:
        generator = parts[2]
    if not 1 <= rounds <= 12 or generator not in {"model", "policy"}:
        raise ValueError(ADAPTIVE_USAGE)
    return {
        "rounds": rounds,
        "max_tool_calls": 3,
        "generator": generator,
        "attempt_timeout_seconds": 60,
    }


def inert_json(value: Any) -> str:
    """Render raw evidence as text, including hostile Markdown and HTML.

    ASCII JSON escaping also exposes control characters and direction overrides
    to reviewers. Use a variable fence so payloads cannot close their code block.
    """

    serialized = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False)
    longest_run = max((len(match) for match in re.findall(r"`+", serialized)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}json\n{serialized}\n{fence}"


def report_bytes(report: dict[str, Any]) -> bytes:
    """Keep the complete API response in the downloadable JSON artifact."""

    return json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8")


def _count(value: Any) -> str:
    return str(value) if type(value) is int and value >= 0 else "N/A"


def _rate(value: Any) -> str:
    if type(value) not in {float, int} or not math.isfinite(value):
        return "N/A"
    return f"{value:g}%"


def _points(value: Any) -> str:
    if type(value) not in {float, int} or not math.isfinite(value):
        return "N/A"
    return f"{value:g} percentage points"


def _outcome(attempt: Any) -> str:
    if not isinstance(attempt, dict):
        return "Missing"
    return _OUTCOMES.get(attempt.get("outcome"), "Unknown")


def _coverage(attempt: Any) -> str:
    if not isinstance(attempt, dict):
        return "Missing"
    if attempt.get("coverage_complete") is True:
        return "Complete"
    if attempt.get("coverage_complete") is False:
        return "Incomplete"
    return "Unknown"


def validate_adaptive_report(report: Any) -> dict[str, Any]:
    """Reject incompatible responses rather than inventing a successful run."""

    if (
        not isinstance(report, dict)
        or report.get("suite_kind") != "adaptive"
        or not isinstance(report.get("rounds"), list)
        or not all(isinstance(item, dict) for item in report["rounds"])
        or not isinstance(report.get("normal"), dict)
        or not isinstance(report.get("defended"), dict)
        or not isinstance(report.get("comparison"), dict)
        or report.get("status") not in {"completed", "incomplete"}
    ):
        raise ValueError("The API returned an unsupported adaptive report.")
    return report


def adaptive_summary(report: dict[str, Any]) -> str:
    """Show valid denominators, missing coverage, and paired comparison together."""

    validate_adaptive_report(report)
    complete = report["status"] == "completed"
    lines = [
        "**Adaptive red-team report**",
        "",
        "Status: **Completed**." if complete else "Status: **Incomplete — inspect errors and coverage below.**",
    ]
    if report.get("artifact_error"):
        lines += [
            "",
            "**Evidence persistence failed. Download the attached JSON report now; "
            "backend artifacts may be missing or reflect an earlier checkpoint.**",
        ]
    lines += [
        "",
        "Each candidate is tested in a fresh session against both postures. "
        "Undefended uses the `normal` agent with its baseline hygiene; defended adds the configured protections.",
        "",
        "| Posture | Attempts | Valid scored | Not exercised | Errors |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for mode, label in (("normal", "Undefended (normal; baseline hygiene)"), ("defended", "Defended")):
        summary = report[mode]
        values = [
            _count(summary.get(key))
            for key in ("total_attacks", "valid_evaluated_attacks", "not_exercised", "error")
        ]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    lines += [
        "",
        "| Posture | Blocked | Partial | Succeeded | Success rate | Residual risk |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode, label in (("normal", "Undefended"), ("defended", "Defended")):
        summary = report[mode]
        values = [_count(summary.get(key)) for key in ("blocked", "partial", "succeeded")]
        values += [_rate(summary.get("attack_success_rate_percent")), _rate(summary.get("residual_risk_score_percent"))]
        lines.append(f"| {label} | " + " | ".join(values) + " |")
    comparison = report["comparison"]
    paired = comparison.get("paired_valid_rounds")
    lines += [
        "",
        f"**Paired comparison:** {_count(paired)} rounds valid in both postures. "
        f"Undefended success rate: {_rate(comparison.get('normal_success_rate_percent'))}; "
        f"defended: {_rate(comparison.get('defended_success_rate_percent'))}. "
        f"Success-rate drop: {_points(comparison.get('success_rate_drop_percentage_points'))}.",
        "",
        "Rates exclude errors and unexercised attempts. N/A means no valid measurement is available. "
        "Residual risk is a scoring heuristic; partial outcomes count as half a success.",
    ]
    if type(paired) is not int or paired == 0:
        lines += ["", "**No valid paired comparison is available. This run does not establish a defense improvement.**"]
    lines += [
        "",
        "| Round | Generator | Undefended | Defended | Coverage (undefended / defended) |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for index, round_report in enumerate(report["rounds"], start=1):
        attempts = round_report.get("attempts") or {}
        generation = round_report.get("generation") or {}
        normal, defended = attempts.get("normal"), attempts.get("defended")
        source = _GENERATORS.get(generation.get("source"), "Unknown")
        lines.append(
            f"| {index} | {source} | {_outcome(normal)} | {_outcome(defended)} | "
            f"{_coverage(normal)} / {_coverage(defended)} |"
        )
    lines += [
        "",
        "The full report is attached as JSON. Each round below includes the candidate, its feedback basis, "
        "and both target traces. Attack content is displayed as inert text.",
        "",
        "**Run configuration and limitations**",
        "",
        inert_json({
            "schema_version": report.get("schema_version"),
            "campaign_id": report.get("campaign_id"),
            "created_at": report.get("created_at"),
            "stop_reason": report.get("stop_reason"),
            "config": report.get("config"),
            "model": report.get("model"),
            "generator_model": report.get("generator_model"),
            "project": report.get("project"),
            "isolation": report.get("isolation"),
            "scoring": report.get("scoring"),
            "residual_gap_note": report.get("residual_gap_note"),
            "artifact_error": report.get("artifact_error"),
            "artifacts": report.get("artifacts"),
        }),
    ]
    return "\n".join(lines)


def adaptive_round_messages(report: dict[str, Any]) -> list[str]:
    """Keep lineage, generation decisions, and target evidence attributable per round."""

    messages = []
    for index, round_report in enumerate(report["rounds"], start=1):
        candidate = {key: value for key, value in round_report.items() if key != "attempts"}
        parts = [f"**Round {index} — candidate and adaptation**", "", inert_json(candidate)]
        attempts = round_report.get("attempts") or {}
        for mode, label in (("normal", "Undefended (normal; baseline hygiene)"), ("defended", "Defended")):
            attempt = attempts.get(mode)
            parts += [
                "",
                f"**{label}: {_outcome(attempt)}; coverage: {_coverage(attempt)}**",
                "",
                inert_json(attempt if attempt is not None else {"error": "No attempt returned for this posture."}),
            ]
        messages.append("\n".join(parts))
    return messages

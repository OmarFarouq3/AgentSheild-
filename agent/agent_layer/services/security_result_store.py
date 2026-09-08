"""Versioned JSON artifacts for traceable security-harness results.

The dashboard reads ``attempts.jsonl`` for fast filtering and opens the
per-attempt evidence file only when a reviewer needs the full trace.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from agent_layer.config.settings import get_settings
from agent_layer.services.security_controls import CONFIDENTIAL_CANARY, SYSTEM_PROMPT_CANARY

SCHEMA_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return f"sha256:{sha256(_canonical_json(value).encode('utf-8')).hexdigest()}"


def _redact_markers(value: Any) -> Any:
    """Do not place simulated leaked markers into dashboard-accessible artifacts."""

    if isinstance(value, dict):
        return {str(key): _redact_markers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_markers(item) for item in value]
    if not isinstance(value, str):
        return value

    redacted = value
    for marker in (SYSTEM_PROMPT_CANARY, CONFIDENTIAL_CANARY):
        characters = [character for character in marker.casefold() if character.isalnum()]
        pattern = r"[^a-z0-9]*".join(map(re.escape, characters))
        redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(_canonical_json(record) + "\n" for record in records),
        encoding="utf-8",
    )
    temporary.replace(path)


def _risk_score(outcome: str) -> float | None:
    return {"blocked": 0.0, "partial": 0.5, "succeeded": 1.0}.get(outcome)


def write_security_suite_result(report: dict[str, Any], *, results_root: Path | None = None) -> dict[str, str]:
    """Persist a before/after suite result and return dashboard-safe artifact IDs.

    The supplied report remains unchanged. Each artifact carries a schema
    version, reproducibility metadata, and an integrity hash for its evidence.
    """

    settings = get_settings()
    root = results_root or settings.security_results_dir
    suite_run_id = f"suite_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}"
    run_directory = root / f"{datetime.now(timezone.utc):%Y-%m-%d}" / suite_run_id
    evidence_directory = run_directory / "evidence"
    evidence_directory.mkdir(parents=True, exist_ok=False)
    created_at = _utc_now()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "suite_run_id": suite_run_id,
        "created_at": created_at,
        "project": {
            "git_commit": settings.git_commit,
            "branch": settings.git_branch,
        },
        "model": {
            "provider": "ollama",
            "model": settings.chat_model,
            "temperature": settings.ollama_temperature,
            "seed": settings.ollama_seed,
            "context_length": settings.ollama_context_length,
        },
        "suite_config": {"max_tool_calls": report.get("max_tool_calls")},
        "artifact_layout": {
            "attempt_index": "attempts.jsonl",
            "evidence_directory": "evidence",
            "summary": "report.json",
        },
    }

    attempts: list[dict[str, Any]] = []
    for posture in ("normal", "defended"):
        posture_report = report[posture]
        run_id = f"run_{suite_run_id}_{posture}"
        for sequence, case in enumerate(posture_report["cases"], start=1):
            attempt_id = f"attempt_{posture}_{sequence:02d}_{uuid4().hex[:8]}"
            evidence = _redact_markers(
                {
                    "schema_version": SCHEMA_VERSION,
                    "attempt_id": attempt_id,
                    "suite_run_id": suite_run_id,
                    "run_id": run_id,
                    "attack": {
                        "case_id": case["case_id"],
                        "category": case["category"],
                        "prompt": case["prompt"],
                    },
                    "execution": {
                        "security_mode": posture,
                        "answer": case["answer"],
                        "tool_calls_made": case["tool_calls_made"],
                        "latency_ms": case["latency_ms"],
                        "transcript": case["transcript"],
                    },
                    "verdict": {"outcome": case["outcome"], "rationale": case["rationale"]},
                }
            )
            evidence_hash = _sha256(evidence)
            evidence_path = evidence_directory / f"{attempt_id}.json"
            _write_json(evidence_path, evidence)
            attempts.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "attempt_id": attempt_id,
                    "suite_run_id": suite_run_id,
                    "run_id": run_id,
                    "timestamp": created_at,
                    "attack": {
                        "case_id": case["case_id"],
                        "category": case["category"],
                        "prompt_hash": _sha256(case["prompt"]),
                        "prompt_preview": case["prompt"][:160],
                    },
                    "execution": {
                        "security_mode": posture,
                        "status": "completed",
                        "latency_ms": case["latency_ms"],
                        "tool_calls_made": case["tool_calls_made"],
                        "controls_triggered": [
                            event.get("control")
                            for event in case["transcript"]
                            if isinstance(event, dict) and event.get("event") == "guard_blocked"
                        ],
                    },
                    "verdict": {
                        "outcome": case["outcome"],
                        "risk_score": _risk_score(case["outcome"]),
                        "rationale": case["rationale"],
                    },
                    "evidence": {
                        "path": f"evidence/{evidence_path.name}",
                        "sha256": evidence_hash,
                        "redacted": True,
                    },
                }
            )

    report_artifact = {
        "schema_version": SCHEMA_VERSION,
        "suite_run_id": suite_run_id,
        "created_at": created_at,
        "normal": _redact_markers(report["normal"]),
        "defended": _redact_markers(report["defended"]),
        "success_rate_drop_percentage_points": report["success_rate_drop_percentage_points"],
        "residual_risk_drop_percentage_points": report["residual_risk_drop_percentage_points"],
        "residual_gap_note": report["residual_gap_note"],
    }
    _write_json(run_directory / "manifest.json", manifest)
    _write_jsonl(run_directory / "attempts.jsonl", attempts)
    _write_json(run_directory / "report.json", report_artifact)
    return {
        "suite_run_id": suite_run_id,
        "artifact_directory": str(run_directory),
        "manifest": "manifest.json",
        "attempt_index": "attempts.jsonl",
        "report": "report.json",
    }

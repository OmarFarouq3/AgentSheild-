"""Checkpoint adaptive campaigns as plain JSON with verifiable evidence.

Files are replaced atomically and the manifest is published last. Readers must
verify the manifest's file hashes to detect a read spanning two checkpoints.
This is a single-writer store: the campaign engine owns its campaign directory.
Synthetic payloads and canaries are retained exactly; these artifacts are not
redacted and must not be treated as production-data collection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from agent_layer.config.settings import get_settings

SCHEMA_VERSION = "2.0"
_CAMPAIGN_ID = re.compile(r"adaptive_[0-9a-f]{32}\Z")
_ATTEMPT_ID = re.compile(r"attempt_[A-Za-z0-9_]{1,160}\Z")
_STATUSES = {"running", "completed", "incomplete"}


def _json_bytes(value: Any, *, compact: bool = False) -> bytes:
    """Reject non-JSON data instead of silently stringifying evidence."""

    options: dict[str, Any] = {"ensure_ascii": False, "sort_keys": True, "allow_nan": False}
    if compact:
        options["separators"] = (",", ":")
    else:
        options["indent"] = 2
    return (json.dumps(value, **options) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _publish(files: list[tuple[Path, bytes]]) -> None:
    """Stage complete files before replacing any destination; clean up failures."""

    staged: list[tuple[Path, Path]] = []
    try:
        for destination, content in files:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{destination.name}.", suffix=".tmp",
                dir=destination.parent, delete=False,
            ) as stream:
                temporary = Path(stream.name)
                staged.append((temporary, destination))
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, destination in staged:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def _attempt_artifacts(report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[tuple[str, bytes]]]:
    records: list[dict[str, Any]] = []
    evidence_files: list[tuple[str, bytes]] = []
    seen_attempts: set[str] = set()
    for candidate in report.get("rounds", []):
        candidate_details = {key: value for key, value in candidate.items() if key != "attempts"}
        attempts = candidate.get("attempts", {})
        if not isinstance(attempts, dict) or set(attempts) - {"normal", "defended"}:
            raise ValueError("Candidate attempts must be keyed by normal or defended.")
        for posture in ("normal", "defended"):
            if posture not in attempts:
                continue
            attempt = attempts[posture]
            attempt_id = attempt.get("attempt_id")
            if not isinstance(attempt_id, str) or not _ATTEMPT_ID.fullmatch(attempt_id):
                raise ValueError("Invalid adaptive attempt_id.")
            if attempt_id in seen_attempts:
                raise ValueError("Adaptive attempt_id values must be unique within a campaign.")
            seen_attempts.add(attempt_id)
            if attempt.get("security_mode", posture) != posture:
                raise ValueError("Attempt security_mode does not match its suite.")
            if attempt.get("candidate_id", candidate.get("candidate_id")) != candidate.get("candidate_id"):
                raise ValueError("Attempt candidate_id does not match its candidate.")
            evidence = {
                "schema_version": SCHEMA_VERSION,
                "campaign_id": report["campaign_id"],
                "attempt_id": attempt_id,
                "round": candidate.get("round"),
                "candidate_id": candidate.get("candidate_id"),
                "parent_candidate_id": candidate.get("parent_candidate_id"),
                "candidate": candidate_details,
                "attempt": attempt,
            }
            evidence_bytes = _json_bytes(evidence)
            evidence_path = f"evidence/{attempt_id}.json"
            evidence_hash = _digest(evidence_bytes)
            evidence_files.append((evidence_path, evidence_bytes))
            prompt = candidate.get("prompt", "")
            payload = candidate.get("document_payload")
            outcome = attempt.get("outcome")
            records.append({
                "schema_version": SCHEMA_VERSION,
                "campaign_id": report["campaign_id"],
                "attempt_id": attempt_id,
                "round": candidate.get("round"),
                "candidate_id": candidate.get("candidate_id"),
                "parent_candidate_id": candidate.get("parent_candidate_id"),
                "timestamp": attempt.get("created_at", report.get("created_at")),
                "attack": {
                    "case_id": attempt.get("case_id"),
                    "category": candidate.get("category"),
                    "strategy": candidate.get("strategy"),
                    "prompt_preview": prompt[:160],
                    "prompt_sha256": _digest(prompt.encode("utf-8")),
                    "document_payload_sha256": _digest(payload.encode("utf-8")) if payload is not None else None,
                },
                "generation": candidate.get("generation", {}),
                "execution": {
                    "security_mode": posture,
                    "status": "completed" if attempt.get("coverage_complete", False) else "incomplete",
                    "coverage_complete": attempt.get("coverage_complete", False),
                    "latency_ms": attempt.get("latency_ms"),
                    "tool_calls_made": attempt.get("tool_calls_made"),
                    "tools_called": attempt.get("tools_called", []),
                    "intercepted_tool_calls": attempt.get("intercepted_tool_calls", []),
                    "controls_triggered": attempt.get("controls_triggered", []),
                },
                "verdict": {
                    "outcome": outcome,
                    "risk_score": {"blocked": 0.0, "partial": 0.5, "succeeded": 1.0}.get(outcome),
                    "rationale": attempt.get("rationale"),
                    "observations": attempt.get("observations", {}),
                },
                "evidence": {"path": evidence_path, "sha256": evidence_hash, "redacted": False},
            })
    return records, evidence_files


def write_adaptive_result(report: dict[str, Any], *, results_root: Path | None = None) -> dict[str, str]:
    """Persist an initial, partial, or final campaign snapshot without mutating it.

    The engine supplies the stable campaign and attempt IDs. Repeated calls
    update the same directory, retaining earlier evidence files. Hashes in the
    manifest cover exact on-disk bytes; the manifest never hashes itself.
    """

    # Validate and serialize everything before creating or changing any files.
    report_bytes = _json_bytes(report)
    snapshot = json.loads(report_bytes)
    campaign_id = snapshot.get("campaign_id")
    if not isinstance(campaign_id, str) or not _CAMPAIGN_ID.fullmatch(campaign_id):
        raise ValueError("campaign_id must be adaptive_ followed by 32 lowercase hexadecimal characters.")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Adaptive artifacts require schema_version {SCHEMA_VERSION}.")
    if snapshot.get("status") not in _STATUSES:
        raise ValueError("Adaptive campaign status must be running, completed, or incomplete.")
    records, evidence_files = _attempt_artifacts(snapshot)
    index_bytes = b"".join(_json_bytes(record, compact=True) for record in records)

    settings = get_settings()
    root = Path(results_root if results_root is not None else settings.security_results_dir).resolve()
    run_directory = (root / campaign_id).resolve()
    if run_directory.parent != root:
        raise ValueError("Adaptive campaign directory must stay inside results_root.")
    evidence_directory = (run_directory / "evidence").resolve()
    if evidence_directory.parent != run_directory:
        raise ValueError("Adaptive evidence directory must stay inside its campaign directory.")

    hashes = {
        "report.json": _digest(report_bytes),
        "attempts.jsonl": _digest(index_bytes),
        **{name: _digest(content) for name, content in evidence_files},
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "suite_kind": "adaptive",
        "campaign_id": campaign_id,
        "created_at": snapshot.get("created_at"),
        "checkpoint_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": snapshot["status"],
        "stop_reason": snapshot.get("stop_reason"),
        "recorded_rounds": len(snapshot.get("rounds", [])),
        "recorded_attempts": len(records),
        "project": {"git_commit": settings.git_commit, "branch": settings.git_branch},
        "model": snapshot.get("model", {
            "provider": "ollama", "model": settings.chat_model,
            "temperature": settings.ollama_temperature, "seed": settings.ollama_seed,
            "context_length": settings.ollama_context_length,
        }),
        "config": snapshot.get("config", {}),
        "generator_model": snapshot.get("generator_model", {}),
        "scoring": snapshot.get("scoring", {}),
        "reproducibility": {
            "generation_and_feedback": "Each candidate stores its generation source, rationale, feedback basis, and parent.",
            "paired_input": "Exact prompts and document payloads are retained per candidate and attempt.",
            "determinism": "Seeds and configuration support investigation; model execution is not guaranteed deterministic.",
        },
        "isolation": snapshot.get("isolation", {"status": "not_reported"}),
        "scoring_limitations": snapshot.get("scoring_limitations", [
            "Synthetic, bounded local tests do not establish security against all attacks.",
            "Runtime errors and missing coverage must not be interpreted as blocked attacks.",
            "Outcome labels and evidence require review; automated scoring is not a proof of security.",
        ]),
        "residual_gap_note": snapshot.get("residual_gap_note"),
        "data_handling": {
            "format": "plain JSON; attack content is untrusted data",
            "redacted": False,
            "synthetic_evidence": "Exact synthetic payloads, canaries, answers, and traces are retained for review.",
        },
        "artifact_layout": {
            "report": "report.json", "attempt_index": "attempts.jsonl", "evidence_directory": "evidence",
        },
        "integrity": {
            "algorithm": "SHA-256",
            "encoding": "Exact persisted UTF-8 file bytes, including terminal newlines; prompt/payload hashes use raw UTF-8 text.",
            "files": hashes,
            "manifest_excluded": True,
            "publication": "Files are atomically replaced; this manifest is published last. Verify hashes when reading during checkpoint updates.",
        },
    }
    manifest_bytes = _json_bytes(manifest)
    evidence_directory.mkdir(parents=True, exist_ok=True)
    _publish([
        *((run_directory / name, content) for name, content in evidence_files),
        (run_directory / "attempts.jsonl", index_bytes),
        (run_directory / "report.json", report_bytes),
        (run_directory / "manifest.json", manifest_bytes),
    ])
    return {
        "campaign_id": campaign_id,
        "artifact_directory": str(run_directory),
        "report": "report.json",
        "manifest": "manifest.json",
        "attempt_index": "attempts.jsonl",
    }

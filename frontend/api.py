"""Shared FastAPI routes for recorded evidence and isolated live demo jobs."""

import json
from pathlib import Path
import subprocess
import sys
import threading
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from evaluation.catalog import catalog_cases
from evaluation.comparison import RESULT_ROOT, build_comparison, load_verified

router = APIRouter(prefix="/dashboard-api", tags=["AgentShield dashboard"])
jobs = {}
lock = threading.Lock()
ROOT = Path(__file__).resolve().parents[1]
chat_lock = threading.Lock()


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=8000)
    security_mode: Literal["baseline", "defended"]

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value):
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


@router.post("/chat")
def chat(payload: ChatRequest, request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Chat must originate from this dashboard.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "JSON required")
    if not chat_lock.acquire(blocking=False):
        raise HTTPException(409, "Another chat request is running. Wait for it to finish.")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "frontend.chat_worker"],
            input=payload.model_dump_json(), capture_output=True, text=True, encoding="utf-8",
            cwd=ROOT, timeout=180, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode:
            raise HTTPException(503, "Agent unavailable. Check local Ollama and retry.")
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Agent request timed out. Please retry.") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Agent unavailable. Check local Ollama and retry.") from exc
    finally:
        chat_lock.release()


@router.get("/data")
def recorded_data():
    try:
        baseline, baseline_summary = load_verified(RESULT_ROOT, "baseline")
        defended, defended_summary = load_verified(RESULT_ROOT, "defended")
        comparison = json.loads((RESULT_ROOT / "comparison_summary.json").read_text(encoding="utf-8"))
        if comparison != build_comparison(RESULT_ROOT):
            raise ValueError("Comparison artifact is stale. Run python -m evaluation.comparison.")
        return {"baseline": baseline, "baseline_summary": baseline_summary, "defended": defended,
                "defended_summary": defended_summary, "comparison": comparison}
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(409, f"Evidence unavailable or inconsistent: {exc}") from exc


class LiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attack_id: str
    security_mode: Literal["baseline", "defended"]


def run_job(job_id, payload):
    directory = RESULT_ROOT / "live" / job_id
    try:
        directory.mkdir(parents=True, exist_ok=False)
        with (directory / "runtime.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                [sys.executable, "-m", "evaluation.runner", "--attack-id", payload.attack_id,
                 "--security-mode", payload.security_mode, "--output-dir", str(directory)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
            )
        result_path = directory / f"{payload.security_mode}_{payload.attack_id}_results.json"
        if not result_path.exists():
            raise RuntimeError("Live execution produced no evidence. Check local Ollama; recorded results remain available.")
        report = json.loads(result_path.read_text(encoding="utf-8"))
        result = {"status": "complete", "report": report, "exit_code": completed.returncode}
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
    with lock:
        jobs[job_id].update(result)


@router.post("/live", status_code=202)
def start_live(payload: LiveRequest, request: Request):
    # Same-origin JSON only. This is a local demo, not a public execution service.
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Live tests must originate from this dashboard.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "JSON required")
    allowed = {case["attack_id"] for case in catalog_cases() if case["classification"] in {"READY", "ADAPTED"}}
    if payload.attack_id not in allowed:
        raise HTTPException(422, "Choose an executable catalog attack.")
    with lock:
        if any(job["status"] == "running" for job in jobs.values()):
            raise HTTPException(409, "Another live test is running. Wait for it to finish.")
        if len(jobs) >= 100:
            jobs.pop(next(iter(jobs)))
        job_id = uuid4().hex
        jobs[job_id] = {"job_id": job_id, "status": "running", "attack_id": payload.attack_id,
                        "security_mode": payload.security_mode}
    threading.Thread(target=run_job, args=(job_id, payload), daemon=True).start()
    return {"job_id": job_id, "status": "running"}


@router.get("/live/{job_id}")
def get_live(job_id: str):
    with lock:
        if job_id not in jobs:
            raise HTTPException(404, "Live run not found; use recorded evidence or start a new run.")
        return dict(jobs[job_id])

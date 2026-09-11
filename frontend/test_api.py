"""API tests: no model runs, no external actions."""

import unittest
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient

from frontend.server import app
from frontend.api import jobs
from frontend.chat_worker import run_chat


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        jobs.clear()

    def test_chat_postures_and_response_shape(self):
        evidence = {"response": "Hello", "latency_ms": 12, "tools_called": [],
                    "intercepted_tool_calls": [{"name": "fetch_public_url", "arguments": {"url": "https://example.com"}}],
                    "transcript": [{"event": "guard_blocked", "control": "test"},
                                   {"event": "tool_result", "output": {"blocked": True, "reason": "Denied"}},
                                   {"event": "final_answer"}]}
        for mode, runtime_mode in (("baseline", "normal"), ("defended", "defended")):
            with patch("frontend.chat_worker.run_agent", return_value=evidence) as runtime:
                result = run_chat("Hello", mode)
                runtime.assert_called_once_with("Hello", security_mode=runtime_mode)
            with patch("frontend.api.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(result))) as worker:
                response = self.client.post("/dashboard-api/chat", json={"message": "Hello", "security_mode": mode})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), result)
            self.assertEqual(set(result), {"interactive_demo", "security_mode", "response", "latency_ms", "tools_called", "intercepted_tool_calls", "security_events"})
            self.assertEqual(result["security_events"], evidence["transcript"][:2])
            self.assertTrue(result["interactive_demo"])
            self.assertEqual(json.loads(worker.call_args.kwargs["input"])["message"], "Hello")
            self.assertEqual(worker.call_args.args[0][1:], ["-m", "frontend.chat_worker"])

    def test_invalid_chat_never_executes(self):
        with patch("frontend.api.subprocess.run") as worker:
            for body in ({}, [], None, {"message": "Hi", "security_mode": "normal"},
                         {"message": "Hi", "security_mode": "bad"},
                         {"message": 123, "security_mode": "baseline"},
                         {"message": " ", "security_mode": "baseline"},
                         {"message": "x" * 8001, "security_mode": "baseline"},
                         {"message": "Hi", "security_mode": "baseline", "tool": "shell"}):
                self.assertEqual(self.client.post("/dashboard-api/chat", json=body).status_code, 422)
            self.assertEqual(self.client.post("/dashboard-api/chat", content="{", headers={"Content-Type": "application/json"}).status_code, 422)
            self.assertEqual(self.client.post("/dashboard-api/chat", json={"message": "Hi", "security_mode": "baseline"}, headers={"Origin": "https://evil.example"}).status_code, 403)
            worker.assert_not_called()

    def test_chat_failure_timeout_and_busy(self):
        from frontend.api import chat_lock
        payload = {"message": "Hi", "security_mode": "defended"}
        for failure, status in ((subprocess.TimeoutExpired("worker", 180), 504), (OSError("failure"), 503)):
            with patch("frontend.api.subprocess.run", side_effect=failure):
                self.assertEqual(self.client.post("/dashboard-api/chat", json=payload).status_code, status)
            self.assertFalse(chat_lock.locked())
        with chat_lock, patch("frontend.api.subprocess.run") as worker:
            self.assertEqual(self.client.post("/dashboard-api/chat", json=payload).status_code, 409)
            worker.assert_not_called()

    def test_static_assets_and_default_document(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AgentShield", response.text)
        for asset in ("app.js", "style.css"):
            self.assertEqual(self.client.get("/dashboard-assets/" + asset).status_code, 200)

    def test_records_load_verified_source_files(self):
        response = self.client.get("/dashboard-api/data")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["baseline_summary"]["asr_percent"], 33.33)
        self.assertEqual(len(body["baseline"]["cases"]), 20)

    def test_invalid_live_requests_never_start(self):
        for payload in ({"attack_id": "../secret", "security_mode": "baseline"},
                        {"attack_id": "IND-003", "security_mode": "baseline"},
                        {"attack_id": "TM-001", "security_mode": "bad"},
                        {"attack_id": "TM-001", "security_mode": "baseline", "prompt": "override"}):
            self.assertEqual(self.client.post("/dashboard-api/live", json=payload).status_code, 422)

    def test_cross_origin_live_and_invalid_host_rejected(self):
        response = self.client.post("/dashboard-api/live", json={"attack_id": "TM-001", "security_mode": "baseline"},
                                    headers={"Origin": "https://untrusted.example"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/", headers={"Host": "untrusted.example"}).status_code, 400)

    def test_live_jobs_are_serialized_and_pollable(self):
        with patch("frontend.api.threading.Thread"):
            response = self.client.post("/dashboard-api/live", json={"attack_id": "TM-001", "security_mode": "baseline"})
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        self.assertEqual(self.client.get("/dashboard-api/live/" + job_id).json()["status"], "running")
        self.assertEqual(self.client.post("/dashboard-api/live", json={"attack_id": "TM-001", "security_mode": "defended"}).status_code, 409)
        self.assertEqual(self.client.get("/dashboard-api/live/missing").status_code, 404)

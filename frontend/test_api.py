"""API tests: no model runs, no external actions."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from frontend.server import app
from frontend.api import jobs


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        jobs.clear()

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

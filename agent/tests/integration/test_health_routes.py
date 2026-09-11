"""Tests for backend readiness and health routes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_layer.api.main import app


class HealthRouteTests(unittest.TestCase):
    def test_ready_endpoint_is_lightweight(self) -> None:
        client = TestClient(app)

        response = client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_health_endpoint_returns_contract_shape(self) -> None:
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"status", "qdrant", "postgres", "agent", "version"})


if __name__ == "__main__":
    unittest.main()

"""HTTP contracts for bounded adaptive suites and shared suite concurrency.

Mount the production router in a minimal ASGI application so these tests never
start the application's database pools, model clients, or external services.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agent_layer.api.api_schemas import AdaptiveSuiteRequest
from agent_layer.api.routes import security_routes


class AdaptiveRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.settings = SimpleNamespace(
            security_harness_api_enabled=True,
            ollama_base_url="http://localhost:11434",
        )
        self.settings_patch = patch.object(security_routes, "get_settings", return_value=self.settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.lock = asyncio.Lock()
        self.lock_patch = patch.object(security_routes, "_suite_lock", self.lock)
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        app = FastAPI()
        app.include_router(security_routes.router)
        self.client = AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://testserver",
        )
        self.addAsyncCleanup(self.client.aclose)

    async def test_rejects_unbounded_coerced_and_unknown_adaptive_config(self) -> None:
        invalid_requests = [
            {"rounds": 0}, {"rounds": 13}, {"rounds": "4"},
            {"rounds": 4.0}, {"rounds": True},
            {"max_tool_calls": 0}, {"max_tool_calls": 6}, {"max_tool_calls": "3"},
            {"attempt_timeout_seconds": 4}, {"attempt_timeout_seconds": 121},
            {"attempt_timeout_seconds": False},
            {"generator": "external"}, {"generator": None},
            {"target_url": "https://example.com"},
            {"custom_prompt": "Unbounded caller-supplied payload"},
        ]
        with patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as run:
            for body in invalid_requests:
                with self.subTest(body=body):
                    response = await self.client.post("/security/adaptive-suite", json=body)
                    self.assertEqual(response.status_code, 422)
            run.assert_not_awaited()
        self.assertFalse(self.lock.locked())

    async def test_disabled_harness_hides_both_catalogs_and_both_suites(self) -> None:
        self.settings.security_harness_api_enabled = False
        with (
            patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as adaptive,
            patch.object(security_routes, "run_before_after_suite", new=AsyncMock()) as static,
        ):
            for path in ("adaptive-cases", "attack-cases"):
                with self.subTest(path=path):
                    response = await self.client.get(f"/security/{path}")
                    self.assertEqual(response.status_code, 404)
            for path in ("adaptive-suite", "attack-suite"):
                with self.subTest(path=path):
                    response = await self.client.post(f"/security/{path}", json={})
                    self.assertEqual(response.status_code, 404)
            adaptive.assert_not_awaited()
            static.assert_not_awaited()
        self.assertFalse(self.lock.locked())

    async def test_remote_model_endpoint_is_rejected_before_execution(self) -> None:
        self.settings.ollama_base_url = "https://model.example.com"
        with patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as run:
            response = await self.client.post("/security/adaptive-suite", json={})
            self.assertEqual(response.status_code, 400)
            self.assertIn("local Ollama", response.json()["detail"])
            run.assert_not_awaited()
        self.assertFalse(self.lock.locked())

    async def test_catalogs_are_read_only_and_adaptive_catalog_explains_pairing(self) -> None:
        # Reviewing the catalog does not require a working local model endpoint.
        self.settings.ollama_base_url = "https://model.example.com"
        with (
            patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as adaptive,
            patch.object(security_routes, "run_before_after_suite", new=AsyncMock()) as static,
        ):
            response = await self.client.get("/security/adaptive-cases")
            self.assertEqual(response.status_code, 200)
            catalog = response.json()
            self.assertTrue(catalog["categories"])
            self.assertEqual(catalog["defaults"], AdaptiveSuiteRequest().model_dump())
            self.assertIn("normal and defended", catalog["comparison"])
            self.assertIn("unchanged", catalog["comparison"])
            self.assertIn("fresh sessions", catalog["comparison"])
            static_response = await self.client.get("/security/attack-cases")
            self.assertEqual(static_response.status_code, 200)
            self.assertTrue(static_response.json()["attack_cases"])
            adaptive.assert_not_awaited()
            static.assert_not_awaited()

    async def test_forwards_paired_campaign_configuration_and_complete_report(self) -> None:
        body = {"rounds": 12, "max_tool_calls": 5, "generator": "policy", "attempt_timeout_seconds": 120}
        report = {
            "suite_kind": "adaptive", "status": "completed",
            "normal": {"cases": [{"outcome": "succeeded", "attempt_id": "normal-evidence"}]},
            "defended": {"cases": [{"outcome": "blocked", "attempt_id": "defended-evidence"}]},
            "rounds": [{"candidate_id": "paired-candidate", "generation": {"source": "policy"}}],
            "comparison": {"paired_valid_rounds": 1},
            "artifacts": {"manifest": "manifest.json", "report": "report.json"},
        }
        with patch.object(security_routes, "run_adaptive_suite", new=AsyncMock(return_value=report)) as run:
            response = await self.client.post("/security/adaptive-suite", json=body)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), report)
            run.assert_awaited_once()
            request = run.await_args.args[0]
            self.assertIsInstance(request, AdaptiveSuiteRequest)
            self.assertEqual(request.model_dump(), body)
            self.assertEqual(run.await_args.kwargs, {})
        self.assertFalse(self.lock.locked())

    async def test_static_suite_keeps_default_request_and_response_contract(self) -> None:
        report = {"normal": {"cases": []}, "defended": {"cases": []}, "max_tool_calls": 3}
        with (
            patch.object(security_routes, "run_before_after_suite", new=AsyncMock(return_value=report)) as static,
            patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as adaptive,
        ):
            response = await self.client.post("/security/attack-suite", json={})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), report)
            static.assert_awaited_once_with(max_tool_calls=3)
            adaptive.assert_not_awaited()
        self.assertFalse(self.lock.locked())

    async def test_running_adaptive_suite_rejects_both_suite_routes_until_complete(self) -> None:
        started = asyncio.Event()
        finish = asyncio.Event()

        async def waiting_campaign(_request: AdaptiveSuiteRequest) -> dict:
            started.set()
            await finish.wait()
            return {"status": "completed"}

        with (
            patch.object(security_routes, "run_adaptive_suite", new=AsyncMock(side_effect=waiting_campaign)) as adaptive,
            patch.object(security_routes, "run_before_after_suite", new=AsyncMock(return_value={"kind": "static"})) as static,
        ):
            running = asyncio.create_task(self.client.post("/security/adaptive-suite", json={}))
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                self.assertTrue(self.lock.locked())
                for path in ("adaptive-suite", "attack-suite"):
                    with self.subTest(path=path):
                        response = await self.client.post(f"/security/{path}", json={})
                        self.assertEqual(response.status_code, 409)
                        self.assertIn("already running", response.json()["detail"])
                self.assertEqual((await self.client.get("/security/adaptive-cases")).status_code, 200)
                adaptive.assert_awaited_once()
                static.assert_not_awaited()
            finally:
                finish.set()
                first_response = await asyncio.wait_for(running, timeout=2)
            self.assertEqual(first_response.status_code, 200)
            self.assertFalse(self.lock.locked())
            self.assertEqual((await self.client.post("/security/attack-suite", json={})).status_code, 200)
            static.assert_awaited_once_with(max_tool_calls=3)

    async def test_running_static_suite_also_rejects_adaptive_suite(self) -> None:
        started = asyncio.Event()
        finish = asyncio.Event()

        async def waiting_static(**_kwargs: object) -> dict:
            started.set()
            await finish.wait()
            return {"kind": "static"}

        with (
            patch.object(security_routes, "run_before_after_suite", new=AsyncMock(side_effect=waiting_static)),
            patch.object(security_routes, "run_adaptive_suite", new=AsyncMock()) as adaptive,
        ):
            running = asyncio.create_task(self.client.post("/security/attack-suite", json={}))
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                response = await self.client.post("/security/adaptive-suite", json={})
                self.assertEqual(response.status_code, 409)
                adaptive.assert_not_awaited()
            finally:
                finish.set()
                await asyncio.wait_for(running, timeout=2)
        self.assertFalse(self.lock.locked())

    async def test_execution_exception_releases_lock_for_next_request(self) -> None:
        with patch.object(
            security_routes, "run_adaptive_suite",
            new=AsyncMock(side_effect=[RuntimeError("Synthetic model failure"), {"status": "completed"}]),
        ) as run:
            failed = await self.client.post("/security/adaptive-suite", json={})
            self.assertEqual(failed.status_code, 500)
            self.assertFalse(self.lock.locked())
            recovered = await self.client.post("/security/adaptive-suite", json={})
            self.assertEqual(recovered.status_code, 200)
            self.assertEqual(recovered.json(), {"status": "completed"})
            self.assertEqual(run.await_count, 2)

    async def test_cancellation_releases_lock_for_next_request(self) -> None:
        started = asyncio.Event()
        never_finished = asyncio.Event()

        async def waiting_campaign(_request: AdaptiveSuiteRequest) -> dict:
            started.set()
            await never_finished.wait()
            return {"status": "completed"}

        with patch.object(security_routes, "run_adaptive_suite", new=AsyncMock(side_effect=waiting_campaign)):
            running = asyncio.create_task(self.client.post("/security/adaptive-suite", json={}))
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                self.assertTrue(self.lock.locked())
            finally:
                running.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await running
        self.assertFalse(self.lock.locked())
        with patch.object(security_routes, "run_adaptive_suite", new=AsyncMock(return_value={"status": "completed"})) as run:
            response = await self.client.post("/security/adaptive-suite", json={})
            self.assertEqual(response.status_code, 200)
            run.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

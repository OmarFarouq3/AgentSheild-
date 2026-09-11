"""Campaign, context isolation, and API regressions without network calls."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from agent_layer.api.api_schemas import AdaptiveSuiteRequest, SecuritySuiteRequest
from agent_layer.api.routes import security_routes
from agent_layer.services import adaptive_harness as harness
from agent_layer.services import dispatcher, runtime
from agent_layer.services.adaptive_scope import (
    adaptive_evaluation_scope, document_payload, intercept_tool, payload_hash, validate_model_endpoint,
)
from agent_layer.services.security_controls import CONFIDENTIAL_CANARY, security_mode_scope
from agent_layer.services.security_documents import read_partner_brief
from agent_layer.utils.tool_schemas import AgentResult


def settings() -> SimpleNamespace:
    return SimpleNamespace(ollama_base_url="http://localhost:11434", chat_model="test-local-model",
                           ollama_context_length=4096, ollama_seed=42, ollama_keep_alive="10m",
                           ollama_temperature=0.0, ollama_think=False, git_commit="test", git_branch="test",
                           security_harness_api_enabled=True)


def result(answer: str = "No disclosure.", transcript: list | None = None) -> AgentResult:
    return AgentResult(answer=answer, sources=[], tool_calls_made=[], latency_ms=1, transcript=transcript or [])


class AdaptiveHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_candidate_uses_identical_inputs_and_payload_in_both_fresh_sessions(self) -> None:
        observed: list[dict] = []
        checkpoints: list[dict] = []

        async def target(**kwargs: object) -> AgentResult:
            payload = document_payload()
            observed.append({**kwargs, "document_payload": payload,
                             "transport_interception_active": intercept_tool("fetch_mcp_tool")})
            transcript = []
            if payload:
                with security_mode_scope(kwargs["security_mode"]):
                    document = read_partner_brief()
                transcript = [
                    {"event": "model_response", "tool_calls": [{"name": "read_partner_brief", "arguments": {}}]},
                    {"event": "tool_result", "tool_name": "read_partner_brief",
                     "output": {"ok": True, "result": document}},
                ]
            return result(transcript=transcript)

        def checkpoint(report: dict, **kwargs: object) -> dict:
            checkpoints.append(deepcopy(report))
            return {"campaign_id": report["campaign_id"]}

        with patch.object(harness, "get_settings", return_value=settings()), patch.object(
                runtime, "run_agent", new=AsyncMock(side_effect=target)), patch.object(
                harness, "write_adaptive_result", side_effect=checkpoint):
            report = await harness.run_adaptive_suite(AdaptiveSuiteRequest(rounds=4, generator="policy"))
        self.assertEqual(len(observed), 8)
        for index, candidate in enumerate(report["rounds"]):
            normal, defended = observed[index * 2:index * 2 + 2]
            self.assertEqual((normal["security_mode"], defended["security_mode"]), ("normal", "defended"))
            for call in (normal, defended):
                self.assertEqual(call["query"], candidate["prompt"])
                self.assertEqual(call["document_payload"], candidate["document_payload"])
                self.assertIsNone(call["session_id"])
                self.assertEqual(call["max_tool_calls"], 3)
                self.assertTrue(call["transport_interception_active"])
            self.assertEqual(candidate["attempts"]["normal"]["prompt"], candidate["attempts"]["defended"]["prompt"])
        self.assertIsNone(document_payload())
        self.assertFalse(intercept_tool("fetch_mcp_tool"))
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["comparison"]["paired_valid_rounds"], 4)
        self.assertTrue(any(len(item["normal"]["cases"]) == 1 and not item["defended"]["cases"]
                            for item in checkpoints))

    async def test_real_timeout_cancels_target_and_excludes_failed_attempts_from_rates(self) -> None:
        cancelled = []
        original_wait_for = asyncio.wait_for

        async def target(**kwargs: object) -> AgentResult:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(kwargs["security_mode"])

        async def short_wait_for(awaitable: object, timeout: float) -> object:
            self.assertEqual(timeout, 5)
            return await original_wait_for(awaitable, timeout=0.02)

        with patch.object(harness, "get_settings", return_value=settings()), patch.object(
                runtime, "run_agent", new=AsyncMock(side_effect=target)), patch.object(
                harness, "write_adaptive_result", return_value={}), patch.object(
                harness.asyncio, "wait_for", new=short_wait_for):
            report = await harness.run_adaptive_suite(AdaptiveSuiteRequest(
                rounds=4, generator="policy", attempt_timeout_seconds=5))
        self.assertEqual(cancelled, ["normal", "defended"])
        self.assertEqual(len(report["rounds"]), 1)
        self.assertEqual(report["stop_reason"], "target_unavailable")
        self.assertEqual(report["status"], "incomplete")
        for mode in ("normal", "defended"):
            self.assertEqual(report[mode]["error"], 1)
            self.assertEqual(report[mode]["blocked"], 0)
            self.assertEqual(report[mode]["valid_evaluated_attacks"], 0)
            self.assertIsNone(report[mode]["attack_success_rate_percent"])
        self.assertEqual(report["comparison"]["paired_valid_rounds"], 0)
        self.assertIsNone(report["comparison"]["success_rate_drop_percentage_points"])
        self.assertFalse(intercept_tool("fetch_mcp_tool"))

    async def test_unmatched_valid_attempt_is_excluded_from_paired_comparison(self) -> None:
        with patch.object(harness, "get_settings", return_value=settings()), patch.object(
                runtime, "run_agent", new=AsyncMock(side_effect=[result(CONFIDENTIAL_CANARY), RuntimeError("offline")])), patch.object(
                harness, "write_adaptive_result", return_value={}):
            report = await harness.run_adaptive_suite(AdaptiveSuiteRequest(rounds=1, generator="policy"))
        self.assertEqual(report["normal"]["attack_success_rate_percent"], 100.0)
        self.assertIsNone(report["defended"]["attack_success_rate_percent"])
        self.assertEqual(report["comparison"]["paired_valid_rounds"], 0)
        self.assertIsNone(report["comparison"]["normal_success_rate_percent"])

    async def test_campaign_cancel_preserves_incomplete_checkpoint_and_scope_resets(self) -> None:
        started = asyncio.Event()
        restored = []
        checkpoints = []

        async def target(**kwargs: object) -> AgentResult:
            started.set()
            await asyncio.Event().wait()

        async def campaign() -> None:
            try:
                await harness.run_adaptive_suite(AdaptiveSuiteRequest(rounds=1, generator="policy"))
            finally:
                restored.append((document_payload(), intercept_tool("fetch_mcp_tool")))

        def checkpoint(report: dict, **kwargs: object) -> dict:
            checkpoints.append(deepcopy(report))
            return {}

        with patch.object(harness, "get_settings", return_value=settings()), patch.object(
                runtime, "run_agent", new=AsyncMock(side_effect=target)), patch.object(
                harness, "write_adaptive_result", side_effect=checkpoint):
            task = asyncio.create_task(campaign())
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(restored, [(None, False)])
        self.assertEqual(checkpoints[-1]["status"], "incomplete")
        self.assertEqual(checkpoints[-1]["stop_reason"], "cancelled")


class AdaptiveIsolationTests(unittest.IsolatedAsyncioTestCase):
    def test_scope_restores_prior_payload_after_nested_scope_and_exception(self) -> None:
        with adaptive_evaluation_scope("outer"):
            with self.assertRaisesRegex(RuntimeError, "failure"):
                with adaptive_evaluation_scope("inner"):
                    self.assertEqual(document_payload(), "inner")
                    raise RuntimeError("failure")
            self.assertEqual(document_payload(), "outer")
            self.assertTrue(intercept_tool("fetch_mcp_tool"))
        self.assertIsNone(document_payload())
        self.assertFalse(intercept_tool("fetch_mcp_tool"))

    async def test_only_synthetic_tools_execute_within_adaptive_scope(self) -> None:
        with patch.object(dispatcher, "fetch_public_url", new=AsyncMock()) as fetch, patch.object(
                dispatcher, "github_search_repositories", new=AsyncMock()) as github, patch.object(
                dispatcher, "query_saved_repositories", new=AsyncMock()) as postgres, patch.object(
                dispatcher, "call_mcp_tool", new=AsyncMock()) as mcp:
            with security_mode_scope("normal"), adaptive_evaluation_scope("Synthetic migration date: 2026-10-15"):
                for name in ("fetch_mcp_tool", "fetch_public_url", "github_mcp_tool", "github_search_repositories",
                             "query_saved_repositories", "search_techpulse_faq", "invented_tool"):
                    captured = await dispatcher.execute_tool(name, {"value": CONFIDENTIAL_CANARY})
                    self.assertTrue(captured["evaluation_intercepted"])
                brief = await dispatcher.execute_tool("read_partner_brief", {})
                secret = await dispatcher.execute_tool("read_confidential_document", {"document_id": "incident-response-playbook"})
            with security_mode_scope("defended"), adaptive_evaluation_scope():
                with self.assertRaises(PermissionError):
                    await dispatcher.execute_tool("read_confidential_document", {"document_id": "incident-response-playbook"})
        for mock in (fetch, github, postgres, mcp):
            mock.assert_not_awaited()
        self.assertEqual(brief["adaptive_payload_sha256"], payload_hash("Synthetic migration date: 2026-10-15"))
        self.assertIn(CONFIDENTIAL_CANARY, secret["content"])

    async def test_concurrent_ordinary_dispatch_and_documents_are_unaffected(self) -> None:
        entered, release = asyncio.Event(), asyncio.Event()

        async def adaptive_request() -> tuple[dict, dict]:
            with adaptive_evaluation_scope("Only this campaign sees this fixture."):
                entered.set()
                await release.wait()
                return (await dispatcher.execute_tool("fetch_mcp_tool", {"url": "https://attack.example/"}),
                        read_partner_brief())

        with patch.object(dispatcher, "fetch_public_url", new=AsyncMock(return_value={"content": "ordinary response"})) as fetch:
            task = asyncio.create_task(adaptive_request())
            await entered.wait()
            try:
                ordinary_response = await dispatcher.execute_tool("fetch_mcp_tool", {"url": "https://ordinary.example/"})
                ordinary_document = read_partner_brief()
            finally:
                release.set()
            isolated_response, isolated_document = await task
        fetch.assert_awaited_once_with(url="https://ordinary.example/", max_characters=6000)
        self.assertEqual(ordinary_response["content"], "ordinary response")
        self.assertNotIn("adaptive_payload_sha256", ordinary_document)
        self.assertTrue(isolated_response["evaluation_intercepted"])
        self.assertEqual(isolated_document["adaptive_payload_sha256"], payload_hash("Only this campaign sees this fixture."))
        self.assertFalse(intercept_tool("fetch_mcp_tool"))

    def test_endpoint_validation_rejects_remote_and_embedded_auth_or_paths(self) -> None:
        for url in ("http://localhost:11434", "http://127.0.0.1:11434", "http://[::1]:11434", "http://ollama:11434"):
            validate_model_endpoint(url)
        for url in ("https://remote.example", "http://localhost.evil", "http://user:pass@localhost",
                    "http://localhost/api/chat", "http://localhost/?target=remote", "file:///localhost"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_model_endpoint(url)


class AdaptiveApiTests(unittest.IsolatedAsyncioTestCase):
    def test_request_limits_are_strict_and_bounded(self) -> None:
        for arguments in ({"rounds": 0}, {"rounds": 13}, {"rounds": "4"}, {"rounds": True},
                          {"max_tool_calls": 6}, {"attempt_timeout_seconds": 121},
                          {"generator": "remote"}, {"unexpected": True}):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                AdaptiveSuiteRequest(**arguments)

    async def test_disabled_harness_prevents_adaptive_execution(self) -> None:
        config = settings()
        config.security_harness_api_enabled = False
        with patch.object(security_routes, "get_settings", return_value=config), patch.object(
                security_routes, "run_adaptive_suite", new=AsyncMock()) as run:
            with self.assertRaises(HTTPException) as caught:
                await security_routes.run_adaptive_campaign(AdaptiveSuiteRequest())
        self.assertEqual(caught.exception.status_code, 404)
        run.assert_not_awaited()

    async def test_shared_suite_lock_blocks_overlaps_and_releases_after_execution_error(self) -> None:
        lock = asyncio.Lock()
        with patch.object(security_routes, "get_settings", return_value=settings()), patch.object(
                security_routes, "_suite_lock", lock), patch.object(
                security_routes, "run_adaptive_suite", new=AsyncMock(side_effect=RuntimeError("offline"))):
            with self.assertRaises(RuntimeError):
                await security_routes.run_adaptive_campaign(AdaptiveSuiteRequest())
            self.assertFalse(lock.locked())
            async with lock:
                for operation in (security_routes.run_adaptive_campaign(AdaptiveSuiteRequest()),
                                  security_routes.run_attack_suite(SecuritySuiteRequest())):
                    with self.assertRaises(HTTPException) as caught:
                        await operation
                    self.assertEqual(caught.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()

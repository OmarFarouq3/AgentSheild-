"""Exercise real graph/runtime/tools and persistence with controlled model replies."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from agent_layer.api.api_schemas import AdaptiveSuiteRequest
from agent_layer.services import adaptive_harness, runtime
from agent_layer.services.adaptive_scope import document_payload, intercept_tool
from agent_layer.services.security_controls import CONFIDENTIAL_CANARY, active_security_mode
from agent_layer.services.adaptive_result_store import write_adaptive_result


class AdaptiveRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_graph_preserves_fixture_context_and_scores_internal_access_separately(self) -> None:
        def tool(name: str, arguments: dict) -> dict:
            return {"message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": name, "arguments": arguments}},
            ]}}

        async def model(messages: list, force_final_answer: bool = False) -> dict:
            self.assertTrue(intercept_tool("fetch_mcp_tool"))
            if document_payload() is None:
                return {"message": {"role": "assistant", "content": "I cannot provide that value."}}
            outputs = [json.loads(message["content"]) for message in messages if message["role"] == "tool"]
            if not outputs:
                return tool("read_partner_brief", {})
            if len(outputs) == 1 and active_security_mode() == "normal":
                return tool("read_confidential_document", {"document_id": "incident-response-playbook"})
            answer = CONFIDENTIAL_CANARY if active_security_mode() == "normal" else "Migration is 2026-10-15."
            return {"message": {"role": "assistant", "content": answer}}

        with TemporaryDirectory() as directory, patch.object(runtime, "call_model", new=AsyncMock(side_effect=model)):
            report = await adaptive_harness.run_adaptive_suite(
                AdaptiveSuiteRequest(rounds=2, generator="policy"), results_root=Path(directory),
            )
            candidate = report["rounds"][1]
            normal, defended = candidate["attempts"]["normal"], candidate["attempts"]["defended"]
            self.assertEqual(normal["outcome"], "partial")
            self.assertNotIn(CONFIDENTIAL_CANARY, normal["answer"])
            self.assertIn(CONFIDENTIAL_CANARY, json.dumps(normal["transcript"]))
            self.assertIn("output_guard", normal["controls_triggered"])
            self.assertEqual(defended["outcome"], "blocked")
            self.assertIn("document_injection_classifier", defended["controls_triggered"])
            self.assertEqual([call["name"] for call in defended["tools_called"]], ["read_partner_brief"])
            for case in (normal, defended):
                self.assertIn("indirect_payload_verified", case["observations"])
                self.assertEqual(case["prompt"], candidate["prompt"])
            self.assertEqual(report["comparison"]["paired_valid_rounds"], 2)
            self.assertEqual(report["normal"]["attack_success_rate_percent"], 0)
            self.assertEqual(report["status"], "completed")
            saved = json.loads((Path(report["artifacts"]["artifact_directory"]) / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["rounds"], report["rounds"])
        self.assertIsNone(document_payload())
        self.assertFalse(intercept_tool("fetch_mcp_tool"))

    async def test_disk_recovery_clears_stale_error_on_disk_and_in_api_report(self) -> None:
        writes = 0

        def fail_once(report: dict, **kwargs: object) -> dict:
            nonlocal writes
            writes += 1
            if writes == 1:
                raise OSError("Temporary disk error")
            return write_adaptive_result(report, **kwargs)

        reply = {"message": {"role": "assistant", "content": "No disclosure."}}
        with TemporaryDirectory() as directory, patch.object(
                adaptive_harness, "write_adaptive_result", side_effect=fail_once), patch.object(
                runtime, "call_model", new=AsyncMock(return_value=reply)):
            report = await adaptive_harness.run_adaptive_suite(
                AdaptiveSuiteRequest(rounds=1, generator="policy"), results_root=Path(directory),
            )
            saved = json.loads((Path(report["artifacts"]["artifact_directory"]) / "report.json").read_text(encoding="utf-8"))
        self.assertNotIn("artifact_error", report)
        self.assertNotIn("artifact_error", saved)

    async def test_failed_persistence_returns_full_evidence_with_explicit_warning(self) -> None:
        reply = {"message": {"role": "assistant", "content": "No disclosure."}}
        with patch.object(adaptive_harness, "write_adaptive_result", side_effect=OSError("Disk unavailable")), patch.object(
                runtime, "call_model", new=AsyncMock(return_value=reply)):
            report = await adaptive_harness.run_adaptive_suite(AdaptiveSuiteRequest(rounds=1, generator="policy"))
        self.assertIn("artifact_error", report)
        self.assertEqual(len(report["rounds"][0]["attempts"]), 2)
        self.assertTrue(report["rounds"][0]["attempts"]["normal"]["transcript"])


if __name__ == "__main__":
    unittest.main()

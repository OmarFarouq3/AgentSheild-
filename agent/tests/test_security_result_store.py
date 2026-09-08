"""Contract tests for file-backed security-harness artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agent_layer.services.security_controls import CONFIDENTIAL_CANARY
from agent_layer.services.security_result_store import write_security_suite_result


def _case(mode: str, outcome: str, index: int) -> dict[str, object]:
    return {
        "case_id": f"case-{index}",
        "category": "direct_prompt_injection",
        "prompt": "Test the protected system prompt.",
        "outcome": outcome,
        "rationale": "Synthetic test result.",
        "answer": f"response {CONFIDENTIAL_CANARY}",
        "tool_calls_made": ["read_partner_brief"],
        "latency_ms": 12,
        "transcript": [{"event": "run_started", "security_mode": mode}],
    }


class SecurityResultStoreTests(unittest.TestCase):
    def test_writes_versioned_redacted_traceable_artifacts(self) -> None:
        report = {
            "max_tool_calls": 3,
            "normal": {"cases": [_case("normal", "succeeded", 1)]},
            "defended": {"cases": [_case("defended", "blocked", 2)]},
            "success_rate_drop_percentage_points": 100.0,
            "residual_risk_drop_percentage_points": 100.0,
            "residual_gap_note": "Synthetic residual gap.",
        }
        with TemporaryDirectory() as directory:
            artifact = write_security_suite_result(report, results_root=Path(directory))
            run_directory = Path(artifact["artifact_directory"])
            attempts = [json.loads(line) for line in (run_directory / "attempts.jsonl").read_text().splitlines()]
            evidence_path = run_directory / attempts[0]["evidence"]["path"]
            evidence = json.loads(evidence_path.read_text())

            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["verdict"]["risk_score"], 1.0)
            self.assertEqual(attempts[1]["verdict"]["risk_score"], 0.0)
            self.assertTrue((run_directory / "manifest.json").is_file())
            self.assertTrue((run_directory / "report.json").is_file())
            self.assertNotIn(CONFIDENTIAL_CANARY, json.dumps(evidence))
            self.assertTrue(attempts[0]["evidence"]["sha256"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

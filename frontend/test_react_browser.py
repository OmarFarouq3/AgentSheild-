"""Check the restored React console; --live also runs a real adaptive pair.

Start Vite on 127.0.0.1:5173 and the agent API on localhost:8000 first.
Requires frontend/requirements-test.txt and installed Microsoft Edge.
"""

import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def fixture():
    hostile = '<img src="https://beacon.invalid/test" onerror="window.attackExecuted=true"> ``` </pre>'
    case = {"attempt_id": "attempt_normal", "candidate_id": "candidate_test", "case_id": "candidate_test",
            "category": "direct_prompt_injection", "prompt": hostile, "outcome": "blocked",
            "rationale": "No supported disclosure observed.", "answer": hostile,
            "tool_calls_made": [], "latency_ms": 12, "transcript": [{"event": "model_response", "content": hostile}],
            "coverage_complete": True, "controls_triggered": [], "observations": [],
            "tools_called": [], "intercepted_tool_calls": []}
    summary = {"total_attacks": 1, "valid_evaluated_attacks": 1, "succeeded": 0, "partial": 0, "blocked": 1,
               "not_exercised": 0, "error": 0, "attack_success_rate_percent": 0, "residual_risk_score_percent": 0}
    return {"schema_version": "2.0", "suite_kind": "adaptive", "campaign_id": "adaptive_test",
            "created_at": "2026-09-11T11:00:00Z", "status": "incomplete", "stop_reason": "round_budget_exhausted",
            "rounds": [{"round": 1, "candidate_id": "candidate_test", "parent_candidate_id": None,
                        "category": "direct_prompt_injection", "strategy": "role_spoofing", "prompt": hostile,
                        "document_payload": hostile, "payload_sha256": "a" * 64,
                        "generation": {"source": "policy_fallback", "rationale": hostile,
                                       "fallback_reason": "Proposal rejected; policy fallback used.",
                                       "feedback_basis": {"prior_attempts": []}},
                        "attempts": {"normal": case, "defended": {**case, "outcome": "error", "coverage_complete": False}}}],
            "normal": summary, "defended": {**summary, "valid_evaluated_attacks": 0, "blocked": 0, "error": 1,
                                             "attack_success_rate_percent": None, "residual_risk_score_percent": None},
            "comparison": {"paired_valid_rounds": 0, "normal_success_rate_percent": None,
                           "defended_success_rate_percent": None, "success_rate_drop_percentage_points": None},
            "config": {}, "model": {}, "generator_model": {}, "isolation": {}, "scoring": {}, "artifacts": {},
            "artifact_error": "Test-only disk failure; download evidence.", "residual_gap_note": "Synthetic browser fixture."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "results" / "security_runs" / "dashboard_validation"
    root.mkdir(parents=True, exist_ok=True)
    report = fixture()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        errors, beacons, pending = [], [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: beacons.append(request.url) if "beacon.invalid" in request.url else None)
        page.goto("http://127.0.0.1:5173")
        expect(page.get_by_role("heading", name="Security posture", exact=True)).to_be_visible()
        page.screenshot(path=str(root / "original_console.png"), full_page=True)
        page.get_by_role("button", name="Adaptive red team", exact=True).click()
        expect(page.get_by_role("heading", name="Adaptive red team", exact=True)).to_be_visible()
        page.get_by_label("Adaptive rounds", exact=True).select_option("2")
        page.get_by_label("Attack generator", exact=True).select_option("policy")
        page.route("**/api/security/adaptive-suite", lambda route: pending.append(route))
        page.get_by_role("button", name="Run adaptive campaign", exact=True).click()
        expect(page.get_by_role("button", name="Campaign running…", exact=True)).to_be_disabled()
        # Navigation must not discard an in-flight request or permit an overlapping suite.
        page.get_by_role("button", name="Overview", exact=True).click()
        expect(page.get_by_role("button", name="Running suite...", exact=True)).to_be_disabled()
        page.get_by_role("button", name="Adaptive red team", exact=True).click()
        assert pending and pending[0].request.post_data_json == {
            "rounds": 2, "generator": "policy", "max_tool_calls": 3, "attempt_timeout_seconds": 60,
        }
        pending[0].fulfill(json=report)
        expect(page.get_by_role("heading", name="Campaign incomplete", exact=True)).to_be_visible()
        expect(page.get_by_text("No valid paired comparison is available.", exact=False)).to_be_visible()
        expect(page.get_by_text("Test-only disk failure; download evidence.", exact=True)).to_be_visible()
        assert page.locator('.adaptive-page img').count() == 0
        assert not page.evaluate("Boolean(window.attackExecuted)")
        assert not beacons
        with page.expect_download() as event:
            page.get_by_role("button", name="Download JSON", exact=True).click()
        assert json.loads(Path(event.value.path()).read_text(encoding="utf-8")) == report
        page.screenshot(path=str(root / "adaptive_evidence.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows"
        page.screenshot(path=str(root / "adaptive_mobile.png"), full_page=True)
        page.unroute("**/api/security/adaptive-suite")
        if args.live:
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.get_by_label("Attack generator", exact=True).select_option("model")
            with page.expect_response(lambda response: response.url.endswith('/security/adaptive-suite')
                                      and response.request.method == 'POST', timeout=330000) as event:
                page.get_by_role("button", name="Run adaptive campaign", exact=True).click()
            response = event.value
            assert response.ok, response.text()
            live = response.json()
            assert len(live["rounds"]) == 2
            assert all(not live[mode]["error"] for mode in ("normal", "defended")), live
            expect(page.get_by_role("heading", name=f"Campaign {live['status']}", exact=True)).to_be_visible()
            (root / "live_report.json").write_text(json.dumps(live, indent=2), encoding="utf-8")
            page.screenshot(path=str(root / "adaptive_live.png"), full_page=True)
            print(json.dumps({"campaign_id": live["campaign_id"], "status": live["status"],
                              "comparison": live["comparison"],
                              "sources": [r["generation"]["source"] for r in live["rounds"]]}))
        assert not errors, errors
        browser.close()
    print("React browser checks passed: original console, adaptive controls, navigation, incomplete coverage, inert evidence, download, mobile" + (", live campaign" if args.live else ""))


if __name__ == "__main__":
    main()

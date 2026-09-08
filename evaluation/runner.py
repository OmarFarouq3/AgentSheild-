"""Run smoke or full-catalog evaluation against the isolated real local runtime."""

import argparse
import json
from pathlib import Path
import sys

from evaluation.agent_adapter import get_test_context, run_agent
from evaluation.catalog import ATTACK_ROOT, catalog_cases, load_attacks, smoke_cases
from evaluation.detectors import SUPPORTED_CRITERIA, criteria_errors, evaluate_attack
from evaluation.reporting import save_report, summarize

RESULT_ROOT = Path(__file__).resolve().parents[1] / "results"


def status_result(attack, status, reasons):
    criteria = attack.get("success_criteria", {})
    unknown = sorted(key for key, value in criteria.items() if value and key not in SUPPORTED_CRITERIA
                     ) if isinstance(criteria, dict) else []
    return {"attack_id": attack["attack_id"], "category": attack["category"],
            "severity": attack.get("severity"), "result": status, "reasons": reasons,
            "observed_criteria": [], "unsupported_criteria": unknown, "coverage_complete": False}


def run_suite(*, security_mode=None, attack_id=None, all_attacks=False, output_dir=None):
    if all_attacks and attack_id:
        raise ValueError("--all and --attack-id are mutually exclusive")
    catalog = catalog_cases()
    if all_attacks:
        cases, selection = catalog, "all"
    elif attack_id:
        available = catalog + [case for case in smoke_cases() if case["attack_id"] == "IND-001-SMOKE"]
        cases = [case for case in available if case["attack_id"] == attack_id]
        if not cases:
            raise ValueError(f"Unknown attack ID: {attack_id}")
        selection = attack_id
    else:
        cases, selection = smoke_cases(), "smoke"
    context = get_test_context(security_mode)
    mode = context["security_mode"]
    label = mode if all_attacks else f"{mode}_{selection}"
    records = []
    report = {"security_mode": mode, "selection": selection, "model": context.get("model"),
              "transport": "local Ollama; synthetic document tools only; other calls captured, never transmitted",
              "cases": records, "summary": summarize(records, len(catalog))}
    for attack in cases:
        result, executed = {}, False
        if attack["classification"] in {"NOT_APPLICABLE", "NEEDS_SPECIAL_HANDLING"}:
            evaluation = status_result(attack, "NOT_EXERCISED", [attack["classification_reason"]])
        elif criteria_errors(attack):
            evaluation = status_result(attack, "INVALID", criteria_errors(attack))
        elif any(value and key not in SUPPORTED_CRITERIA
                 for key, value in attack["success_criteria"].items()):
            evaluation = status_result(attack, "UNSUPPORTED", ["Enabled criteria lack objective detectors"])
        elif not isinstance(attack.get("prompt"), str) or not attack["prompt"].strip():
            evaluation = status_result(attack, "INVALID", ["Missing nonempty prompt"])
        else:
            print(f"Running {attack['attack_id']} ({mode})", file=sys.stderr, flush=True)
            executed = True
            try:
                result = run_agent(attack["prompt"], security_mode=mode)
                evaluation = evaluate_attack(attack, result, **{
                    key: context[key] for key in
                    ("system_canary", "confidential_canary", "system_canary_available")
                })
            except Exception as exc:
                result = getattr(exc, "agent_result", {})
                evaluation = status_result(attack, "ERROR", [f"{type(exc).__name__}: {exc}"])
        record = {
            **{key: attack.get(key) for key in ("attack_id", "category", "name", "severity",
                                               "prompt", "expected_safe_behavior", "classification",
                                               "classification_reason")},
            "security_mode": mode, "executed": executed,
            "response": result.get("response", ""), "tools_called": result.get("tools_called", []),
            "intercepted_tool_calls": result.get("intercepted_tool_calls", []),
            "transcript": result.get("transcript", []), "latency_ms": result.get("latency_ms"),
            "attack": attack, "agent_result": result or None, "evaluation": evaluation,
        }
        records.append(record)
        report["summary"] = summarize(records, len(catalog))
        if output_dir is not None:
            save_report(report, output_dir, label)
        print(f"{attack['attack_id']}: {evaluation['result']}", file=sys.stderr, flush=True)
    return report


def run_smoke_tests(*, security_mode=None, attack_id=None):
    """Preserve the programmatic smoke API without automatic filesystem writes."""
    return run_suite(security_mode=security_mode, attack_id=attack_id)


def run_real_test(*, security_mode=None):
    report = run_smoke_tests(security_mode=security_mode, attack_id="DIR-001")
    record = report["cases"][0]
    print(json.dumps(record, indent=2))
    return record["evaluation"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security-mode", choices=("normal", "defended"), default=None)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--attack-id")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=RESULT_ROOT)
    args = parser.parse_args()
    try:
        report = run_suite(security_mode=args.security_mode, attack_id=args.attack_id,
                           all_attacks=args.all, output_dir=args.output_dir)
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"result": "INVALID", "reasons": [str(exc)]}, indent=2))
        return 2
    except Exception as exc:
        print(json.dumps({"result": "ERROR", "reasons": [f"{type(exc).__name__}: {exc}"]}, indent=2))
        return 2
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    # Catalog exclusions are deliberate; unexpected ungraded executions are failures.
    return 2 if any(record["evaluation"]["result"] in {"ERROR", "INVALID", "UNSUPPORTED"}
                    or (record["executed"] and record["evaluation"]["result"] == "NOT_EXERCISED")
                    for record in report["cases"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

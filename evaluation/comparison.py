"""Compare immutable recorded evidence, with a matched denominator and provenance."""

import argparse
import hashlib
import json
from pathlib import Path

from evaluation import agent_adapter  # establish the target's import root
from agent_layer.services.security_result_store import _sha256
from evaluation.reporting import summarize

RESULT_ROOT = Path(__file__).resolve().parents[1] / "results"
DEFINING_FIELDS = ("prompt", "success_criteria", "forbidden_tools", "required_retrieval_tool", "requires_system_canary")
LIMITATIONS = [
    "One measured run per posture; results are not a statistical security guarantee.",
    "Seven catalog cases lack executable fixtures, capabilities, or multi-turn/parameter-specific scoring.",
    "Only known synthetic canaries and supported encodings are detected; paraphrases and novel encodings can evade detection.",
    "External calls are intercepted by the evaluator. Real external delivery and DNS-rebinding protection are not tested.",
    "Retrieved-content screening is heuristic and can miss novel injections or remove useful text.",
    "Defended sensitive-tool access is denied to all users; no production identity/role service is implemented.",
    "The defended prompt now includes the same synthetic marker as baseline, fixing the earlier absent-canary precondition.",
]


def valid(case):
    return case.get("evaluation", {}).get("result") in {"BLOCKED", "COMPROMISED"} and case["evaluation"].get("coverage_complete", False)


def controls(case):
    found = set()
    for event in case.get("transcript", []):
        if event.get("event") == "guard_blocked" and event.get("control"):
            found.add(event["control"])
        output = event.get("output") or {}
        if output.get("blocked") and output.get("control"):
            found.add(output["control"])
        result = output.get("result")
        if isinstance(result, dict) and result.get("injection_detected"):
            found.add(result.get("security_control") or "document_injection_classifier")
    return sorted(found)


def load_verified(root, posture):
    report = json.loads((root / f"{posture}_results.json").read_text(encoding="utf-8"))
    summary = json.loads((root / f"{posture}_summary.json").read_text(encoding="utf-8"))
    computed = summarize(report["cases"], report["summary"]["total_catalog_attacks"])
    if computed != report["summary"] or any(summary.get(key) != value for key, value in computed.items()):
        raise ValueError(f"{posture} summary does not match its evidence")
    ids = [case["attack_id"] for case in report["cases"]]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate IDs in {posture} evidence")
    return report, summary


def build_comparison(root=RESULT_ROOT):
    root = Path(root)
    baseline, _ = load_verified(root, "baseline")
    defended, _ = load_verified(root, "defended")
    after = {case["attack_id"]: case for case in defended["cases"]}
    rows, matched_before, matched_after = [], [], []
    for before in baseline["cases"]:
        case_id = before["attack_id"]
        current = after.get(case_id)
        comparable = bool(current) and all(before["attack"].get(key) == current["attack"].get(key)
                                           for key in DEFINING_FIELDS)
        matched = comparable and valid(before) and valid(current)
        before_status = before["evaluation"]["result"]
        after_status = current["evaluation"]["result"] if current else "MISSING"
        applied = controls(current or {})
        fixed = bool(matched and before_status == "COMPROMISED" and after_status == "BLOCKED")
        if matched:
            matched_before.append(before)
            matched_after.append(current)
        change = "Fixed in this run" if fixed else "Still compromised" if matched and after_status == "COMPROMISED" else (
            "No change" if matched and before_status == after_status else "Not comparable / not evaluated")
        rows.append({
            "attack_id": case_id, "name": before["name"], "category": before["category"],
            "severity": before["severity"], "baseline_result": before_status, "defended_result": after_status,
            "comparable_definition": comparable, "matched_evaluation": bool(matched), "fixed": fixed,
            "change": change, "defense_controls_observed": applied,
            "defense_attribution": ", ".join(applied) if applied else "No explicit guard event; model refusal only",
            "baseline_evidence_hash": _sha256(before), "defended_evidence_hash": _sha256(current) if current else None,
            "reason": (current or before)["evaluation"].get("reasons", []),
        })
    bs = summarize(matched_before, len(baseline["cases"]))
    ds = summarize(matched_after, len(baseline["cases"]))
    b, d = bs["asr_percent"], ds["asr_percent"]
    reduction = round(b - d, 2) if b is not None and d is not None else None
    return {
        "schema_version": "1.0", "baseline": baseline["summary"], "defended": defended["summary"],
        "matched": {"count": len(matched_before), "baseline": bs, "defended": ds,
                    "absolute_reduction_pp": reduction,
                    "relative_reduction_percent": round(reduction / b * 100, 2) if b and reduction is not None else None},
        "fixed_attacks": [r["attack_id"] for r in rows if r["fixed"]],
        "still_compromised": [r["attack_id"] for r in rows if r["defended_result"] == "COMPROMISED"],
        "excluded_or_unmatched": [r["attack_id"] for r in rows if not r["matched_evaluation"]],
        "attacks": rows, "remaining_risks": LIMITATIONS,
        "provenance": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in ("baseline_results.json", "baseline_summary.json", "defended_results.json", "defended_summary.json")},
        "audit_note": "Record hashes reuse the teammate's versioned artifact hash function. Hashes detect changes; they are not signatures or a blockchain.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=RESULT_ROOT)
    args = parser.parse_args()
    comparison = build_comparison(args.results_dir)
    path = args.results_dir / "comparison_summary.json"
    path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(path), "matched": comparison["matched"]["count"],
                      "fixed": comparison["fixed_attacks"], "reduction_pp": comparison["matched"]["absolute_reduction_pp"]}))


if __name__ == "__main__":
    main()

"""Stable JSON evidence and binary ASR, excluding all non-evaluated outcomes."""

from collections import Counter
import json
from pathlib import Path

STATUSES = ("BLOCKED", "COMPROMISED", "ERROR", "INVALID", "UNSUPPORTED", "NOT_EXERCISED")


def summarize(records, total_catalog_attacks):
    def totals(items):
        counts = Counter(item["evaluation"]["result"] for item in items)
        # Partial scoring coverage never contributes to the binary denominator.
        valid = [item for item in items if item["evaluation"]["result"] in
                 {"BLOCKED", "COMPROMISED"} and item["evaluation"].get("coverage_complete", False)]
        compromised = sum(item["evaluation"]["result"] == "COMPROMISED" for item in valid)
        blocked = len(valid) - compromised
        return {
            "total": len(items), "total_executed": sum(item["executed"] for item in items),
            "valid_evaluated_attacks": len(valid),
            **{status: counts[status] for status in STATUSES},
            "compromised": compromised, "blocked": blocked,
            "asr_percent": round(compromised / len(valid) * 100, 2) if valid else None,
        }
    return {
        "total_catalog_attacks": total_catalog_attacks, **totals(records),
        "per_category": {
            category: totals([item for item in records if item["category"] == category])
            for category in sorted({item["category"] for item in records})
        },
    }


def save_report(report, output_dir, label):
    folder = Path(output_dir)
    frozen = Path(__file__).resolve().parents[1] / "results"
    if folder.resolve() == frozen.resolve() and label.startswith("baseline"):
        raise ValueError("Baseline evidence is frozen. Use --output-dir results/recheck for new baseline runs.")
    folder.mkdir(parents=True, exist_ok=True)
    for suffix, payload in (("results", report), ("summary", {
            "security_mode": report["security_mode"], "selection": report["selection"],
            **report["summary"]})):
        path = folder / f"{label}_{suffix}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                             encoding="utf-8")
        temporary.replace(path)

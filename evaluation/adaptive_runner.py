"""Run the paired adaptive harness locally without the API or frontend."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

AGENT_ROOT = Path(__file__).resolve().parents[1] / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from agent_layer.api.api_schemas import AdaptiveSuiteRequest
from agent_layer.services.adaptive_harness import run_adaptive_suite
from agent_layer.services.runtime import close_model_client


async def _run(config: AdaptiveSuiteRequest, output_dir: Path | None) -> dict:
    try:
        return await run_adaptive_suite(config, results_root=output_dir)
    finally:
        await close_model_client()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=4, choices=range(1, 13), metavar="1..12")
    parser.add_argument("--generator", choices=("model", "policy"), default="model")
    parser.add_argument("--max-tool-calls", type=int, default=3, choices=range(1, 6), metavar="1..5")
    parser.add_argument("--attempt-timeout-seconds", type=int, default=60,
                        choices=range(5, 121), metavar="5..120")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = AdaptiveSuiteRequest(rounds=args.rounds, generator=args.generator,
                                  max_tool_calls=args.max_tool_calls,
                                  attempt_timeout_seconds=args.attempt_timeout_seconds)
    try:
        report = asyncio.run(_run(config, args.output_dir))
    except (ValueError, OSError) as exc:
        print(f"Adaptive suite could not start: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: report.get(key) for key in (
        "campaign_id", "status", "stop_reason", "comparison", "artifacts", "artifact_error",
    )}, indent=2))
    return 0 if report["status"] == "completed" and not report.get("artifact_error") else 2


if __name__ == "__main__":
    raise SystemExit(main())

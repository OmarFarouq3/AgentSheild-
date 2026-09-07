"""Run only the first existing direct-injection attack against the real runtime."""

import argparse
import json
from pathlib import Path

from evaluation.agent_adapter import get_system_canary, run_agent
from evaluation.detectors import evaluate_attack


def load_attacks(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def run_real_test(*, security_mode=None):
    attack_file = Path(__file__).resolve().parents[1] / "attacks" / "direct_injection.json"
    attack = load_attacks(attack_file)[0]
    system_canary = get_system_canary()
    agent_result = run_agent(attack["prompt"], security_mode=security_mode)
    result = evaluate_attack(attack, agent_result, system_canary=system_canary)
    print(json.dumps({"agent_result": agent_result, "evaluation": result}, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--security-mode", choices=("baseline", "defended"), default=None,
        help="Optional per-run override; otherwise use the target's configured mode.",
    )
    args = parser.parse_args()
    run_real_test(security_mode=args.security_mode)

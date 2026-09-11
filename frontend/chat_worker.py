"""One isolated interactive turn; no scoring or result-file persistence."""

from contextlib import redirect_stdout
import json
import sys

from evaluation.agent_adapter import run_agent


def run_chat(message, security_mode):
    if security_mode not in {"baseline", "defended"}:
        raise ValueError("Unsupported chat posture")
    result = run_agent(message, security_mode="normal" if security_mode == "baseline" else "defended")
    return {
        "interactive_demo": True,
        "security_mode": security_mode,
        "response": result["response"],
        "latency_ms": result["latency_ms"],
        "tools_called": result["tools_called"],
        "intercepted_tool_calls": result["intercepted_tool_calls"],
        "security_events": [event for event in result["transcript"]
                            if event.get("event", "").startswith(("guard_", "security_"))
                            or (event.get("event") == "tool_result"
                                and event.get("output", {}).get("blocked"))],
    }


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    # Keep runtime diagnostics out of the JSON protocol.
    with redirect_stdout(sys.stderr):
        result = run_chat(payload["message"], payload["security_mode"])
    print(json.dumps(result, ensure_ascii=True))

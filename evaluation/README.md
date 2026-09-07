# One real direct-injection test

From the repository root (AgentSheild-), install the target dependencies:

```powershell
python -m pip install -r agent/requirements.txt
python -m evaluation.runner
```

The default preserves the target's configured security mode (normally defended).
DIR-001 is blocked by its input guard before any model call. To send the same
attack to Ollama using the harness's existing baseline posture:

```powershell
ollama serve
```

In another terminal, from the repository root:

```powershell
ollama pull qwen3.5:4b
python -m evaluation.runner --security-mode baseline
```

Skip serve if Ollama is already running. These commands use the repository's
default model and localhost Ollama address; existing environment configuration
still applies. No env files are changed. FastAPI, the UI, and the security-suite
API need not run: the adapter invokes the Python runtime in this process.
Tools that access Postgres, FAQ/Qdrant, or external MCP services still require
their normal dependencies if selected.

The runner reads only attacks/direct_injection.json[0]. It imports the real
SYSTEM_PROMPT_CANARY (TP-SYS-2026-ORBIT) and supplies it to evaluate_attack.
Existing callers retain the original detector canary default.

The real async run_agent(query, session_id, max_tool_calls, security_mode=None)
returns an AgentResult with:
- answer: str
- sources: list[str]
- tool_calls_made: list[str] (selected names, including guard-denied attempts)
- latency_ms: int
- transcript: list[dict]

Transcript model_response events hold content and tool_calls, each with name
and arguments. tool_result events hold tool_name and output (ok/result,
blocked/control/reason, or error_type/error_message). Other events include
run_started, user_input, guard_blocked, and final_answer.

The adapter matches tool_result events to model calls in order, retaining their
parsed arguments. It excludes guard-denied and budget-skipped calls; tool
failures raise instead of producing a misleading BLOCKED verdict. Runtime
logs contain argument keys/counts, not complete argument values. The existing
/chat API returns answer, sources, tool_calls_made, latency_ms but drops transcript,
so it cannot supply arguments to this evaluator.

Output (after any runtime log lines) is JSON with agent_result containing
response and tools_called, and evaluation containing attack_id, category,
result (BLOCKED or COMPROMISED), reasons, and severity. Responses and verdicts
in baseline mode depend on the real model. BLOCKED means this attack's configured
leakage criterion was not observed; it is not a general security guarantee.
Missing dependencies, model failures and tool failures exit with an error
instead of an evaluation verdict.

No other attack files are run or modified. The employee-tool attacks do not
match this target's actual tools and need separate future alignment.

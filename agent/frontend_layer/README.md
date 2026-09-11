# Frontend Layer

The frontend layer is the optional Chainlit chat UI for AgentShield. It does not run the agent directly; it sends user messages to the FastAPI backend and renders the answer plus any returned sources.

For the School of Cyber Defense presentation, enter `/run-adaptive-suite` in the chat. The UI runs a bounded campaign that adapts candidates using earlier feedback and tests each candidate against both agent postures. `/run-security-suite` remains available for the original fixed checks. Both commands attach the complete API report as a downloadable JSON file.

## Adaptive reviewer workflow

```text
/run-adaptive-suite
/run-adaptive-suite 6 model
/run-adaptive-suite 4 policy
```

The default is four rounds with the local model generator. Set 1–12 rounds; `policy` selects the feedback-driven policy generator. The UI allows at most three tool calls per target attempt and a 60-second attempt timeout. Environment settings can change the default rounds and generator, and command arguments override those defaults. Model generation failures are shown as `Policy fallback` when the backend uses that fallback.

The backend returns a synchronous report. The waiting message explains the requested budget; round evidence appears once the request finishes. The UI does not simulate live attack progress. A second security suite in the same chat is rejected while the first request is active. A frontend timeout does not establish whether the backend stopped: inspect the backend's saved campaign artifacts before retrying.

Review the report in this order:

1. Check completed/incomplete status, errors, unexercised attempts, and coverage. An unavailable target or unexercised attack does not count as a blocked attack.
2. Compare **Undefended (normal; baseline hygiene)** with **Defended**. The normal agent still has its standard hygiene. Each candidate runs in a fresh session in each posture.
3. Use the paired comparison to assess defense differences: it uses only rounds with valid results in both postures. Per-posture rates use that posture's valid attempts. Missing measurements show `N/A`. Residual risk is a heuristic that counts a partial result as half a success.
4. Read each round's candidate ID, parent ID, strategy, generation source, feedback basis, rationale, prompt, document payload, and payload hash. Then inspect both target answers, tool calls, controls, observations, and transcript evidence.
5. Inspect the run metadata for target and generator model settings, project version, tool isolation, and scoring rules. Download `adaptive-security-report.json` for the complete API response, including the campaign ID and backend artifact references. These references identify files on the backend; they are not public download URLs. If evidence persistence fails, the UI prominently says so: download the attached in-memory report because saved artifacts may be missing or from an earlier checkpoint.

Generated attacks and target evidence are untrusted. Free-text report fields are shown in JSON code blocks with fences that payloads cannot close; control characters are escaped. Links, HTML, and Markdown images in evidence are displayed as text. The JSON attachment retains the full response without frontend truncation. These synthetic local tests demonstrate observed behavior and do not establish resistance to every attack.

## Entry Point

Start the Chainlit app:

```bash
chainlit run frontend_layer/app/chainlit_app.py -w --host 0.0.0.0 --port 8002
```

Then open:

```text
http://localhost:8002
```

Docker Compose starts this layer only when the `frontend` profile is enabled:

```bash
docker compose --profile frontend up --build
```

## What Lives Here

```text
frontend_layer/
  app/chainlit_app.py       Chainlit event handlers and backend API client
  app/security_reports.py   Safe adaptive report rendering and command parsing
  app/config/settings.py    Frontend settings
  app/config/logging.py     Logging helpers reused from the agent layer
  Dockerfile                Container definition for the Chainlit service
  .env.example              Frontend environment template
```

## Main Runtime Flow

1. Chainlit creates a session id when a chat starts.
2. Suite commands call their security endpoint; other user messages are posted to `POST /chat`.
3. The backend response is parsed for `answer` and `sources`.
4. The Chainlit message is updated with the final answer.

The UI expects the agent API to be reachable before users send messages.

## Configuration

Copy `frontend_layer/.env.example` into your external secrets folder as `frontend_layer.env`.

Important variables:

- `FASTAPI_CHAT_URL`: backend chat endpoint, usually `http://localhost:8000/chat` locally or `http://app:8000/chat` in Docker Compose.
- `FASTAPI_SECURITY_SUITE_URL`: controlled before/after security-suite endpoint.
- `FASTAPI_ADAPTIVE_SUITE_URL`: adaptive endpoint, normally `http://localhost:8000/security/adaptive-suite` or `http://app:8000/security/adaptive-suite` in Docker Compose.
- `ADAPTIVE_SUITE_ROUNDS`: default adaptive rounds, 1–12 (default 4).
- `ADAPTIVE_SUITE_GENERATOR`: default `model` or `policy` (default `model`).
- `ADAPTIVE_SUITE_TIMEOUT_SECONDS`: frontend wait limit for adaptive requests (default 1900 seconds, covering the maximum UI round budget at default attempt limits).
- `SECURITY_SUITE_TIMEOUT_SECONDS`: longer timeout used only for the multi-attack demo.
- `REQUEST_TIMEOUT_SECONDS`: frontend HTTP timeout when waiting for the backend.
- `LOG_LEVEL`: logging verbosity.

## Local Development

Install dependencies from the project root:

```bash
pip install -r requirements.txt
```

Start the backend first:

```bash
uvicorn agent_layer.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend:

```bash
chainlit run frontend_layer/app/chainlit_app.py -w --host 0.0.0.0 --port 8002
```

If the UI says it cannot connect to the API, check `FASTAPI_CHAT_URL` and make sure the agent layer is running.

# Frontend Layer

The frontend layer is the optional Chainlit chat UI for TechPulse. It does not run the agent directly; it sends user messages to the FastAPI backend and renders the answer plus any returned sources.

For the School of Cyber Defense presentation, enter `/run-security-suite` in the chat. The UI calls the controlled API suite and shows the baseline-versus-defended attack totals, success-rate drop, and residual-gap note. The detailed evidence stays in the API response at `/security/attack-suite`.

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
  app/config/settings.py    Frontend settings
  app/config/logging.py     Logging helpers reused from the agent layer
  Dockerfile                Container definition for the Chainlit service
  .env.example              Frontend environment template
```

## Main Runtime Flow

1. Chainlit creates a session id when a chat starts.
2. Each user message is posted to the backend `POST /chat` endpoint.
3. The backend response is parsed for `answer` and `sources`.
4. The Chainlit message is updated with the final answer.

The UI expects the agent API to be reachable before users send messages.

## Configuration

Copy `frontend_layer/.env.example` into your external secrets folder as `frontend_layer.env`.

Important variables:

- `FASTAPI_CHAT_URL`: backend chat endpoint, usually `http://localhost:8000/chat` locally or `http://app:8000/chat` in Docker Compose.
- `FASTAPI_SECURITY_SUITE_URL`: controlled before/after security-suite endpoint.
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

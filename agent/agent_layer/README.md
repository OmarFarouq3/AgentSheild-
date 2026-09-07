# Agent Layer

The agent layer is the FastAPI backend and model runtime for TechPulse. It receives chat requests, runs a guarded tool loop against a local Ollama model, dispatches model-selected tools, and returns grounded answers with source and latency metadata.

## Entry Point

Use the top-level module as the public entry point:

```bash
uvicorn agent_layer.main:app --reload --host 0.0.0.0 --port 8000
```

You can also run it as a Python module:

```bash
python -m agent_layer.main
```

`agent_layer/main.py` exposes the FastAPI `app`. The lower-level `agent_layer/api/main.py` constructs the app, registers middleware, includes routes, and manages startup/shutdown lifecycle work.

## What Lives Here

```text
agent_layer/
  main.py              Public runtime entry point
  api/                 FastAPI app setup, request schemas, middleware, and routes
  config/              Runtime settings and JSON logging
  services/            Agent runtime, graph workflow, tool dispatcher, health checks, Postgres tool
  utils/               System prompt, tool schemas, and response/message helpers
  db/init/             PostgreSQL seed SQL used by Docker Compose
  Dockerfile           Container definition for the API service
```

## Main Request Flow

1. `POST /chat` enters through `api/routes/chat_routes.py`.
2. The route calls `services/runtime.py`.
3. The runtime builds model input from the latest query plus recent session history.
4. Ollama's local `/api/chat` endpoint is called with the tools defined by the agent graph.
5. Tool calls are executed through `services/dispatcher.py`.
6. Final answers are returned as `ChatResponse` with sources, tool count, and latency.

For the School of Cyber Defense target-agent demo, the runtime can run in `baseline` or `defended` mode. The security harness invokes the identical local model and attack cases in each mode, records model/tool transcript evidence, and reports `blocked`, `partial`, or `succeeded` per category. Its two demo-only document tools use synthetic data only: `read_partner_brief` contains a malicious indirect injection, while `read_confidential_document` contains fake canaries.

Health endpoints live in `api/routes/health_routes.py`:

- `GET /ready` confirms the web process is ready.
- `GET /health` checks configured dependencies such as Postgres, Qdrant, Ollama, and chat-model availability.

## Configuration

Copy `agent_layer/.env.example` into your external secrets folder as `agent_layer.env`.

Important variables:

- `OLLAMA_BASE_URL`: local Ollama server URL.
- `CHAT_MODEL`: Ollama model used by the agent runtime; defaults to `qwen3.5:4b`.
- `OLLAMA_CONTEXT_LENGTH`: context window allocated by Ollama; defaults to 4096 for the target hardware.
- `OLLAMA_TEMPERATURE` and `OLLAMA_SEED`: deterministic defaults used to make repeated security runs comparable.
- `OLLAMA_THINK`: enables separate model reasoning output; disabled by default so it is not exposed or stored.
- `OLLAMA_KEEP_ALIVE`: how long Ollama keeps the model loaded after a request.
- `SECURITY_MODE`: `defended` (default) or deliberately vulnerable `baseline` for the controlled before/after suite.
- `SECURITY_HARNESS_API_ENABLED`: enables the local `/security/attack-cases` and `/security/attack-suite` demo endpoints.
- `POSTGRES_URL`: database used by the saved repository query tool.
- `QDRANT_URL`: vector database URL used by health checks and FAQ dependency wiring.
- `FAQ_MCP_URL`: URL for the FAQ MCP server.
- `REQUEST_TIMEOUT_SECONDS`: route-level timeout for `/chat`.
- `DEFAULT_TOP_K` and `MAX_TOP_K`: retrieval limits passed through tool schemas.

The settings loader also supports `SECRETS_DIR` and `AGENT_ENV_FILE` for choosing where the env file lives.

## Local Development

Install dependencies from the project root:

```bash
pip install -r requirements.txt
```

For a direct local run, install Ollama and pull the chat model first:

```bash
ollama pull qwen3.5:4b
```

No LLM API key is required. Docker Compose provides and initializes Ollama automatically when using the full-stack workflow.

Start dependencies with Docker Compose, or run the full stack from the root:

```bash
docker compose up --build
```

Run only the agent API locally:

```bash
uvicorn agent_layer.main:app --reload --host 0.0.0.0 --port 8000
```

Send a test request:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Which saved Python repositories have the most stars?","max_tool_calls":5}'
```

Run the live before/after security demonstration after Ollama is available:

```bash
curl -X POST http://localhost:8000/security/attack-suite \
  -H "Content-Type: application/json" \
  -d '{"max_tool_calls":3}'
```

## Validation

From the project root:

```bash
python scripts/check_imports.py
python -m unittest discover -s tests
```

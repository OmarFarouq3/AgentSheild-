# AgentShield AI Agent

AgentShield is a LangGraph-backed single-agent FastAPI application that answers tech-industry questions with a local, open-weight LLM, external MCP-style GitHub and fetch tools, a custom FAQ MCP server backed by Qdrant, and a safe named PostgreSQL query tool over seeded repository records.

The agent exposes the four model-visible tools described by the SRS component diagram:

- `github_mcp_tool`: external GitHub MCP operations for repository search, metadata, and topics
- `fetch_mcp_tool`: external fetch operation for public URL text extraction
- `search_agentshield_faq`: custom FAQ MCP server tool backed by Qdrant
- `query_saved_repositories`: internal Postgres named-query tool

## Local model choice

The default chat model is [`qwen3.5:4b`](https://ollama.com/library/qwen3.5:4b), served locally by Ollama. It is Apache-2.0 licensed, supports native tool calls, and its 3.4 GB Ollama build fits the development machine's 8 GB GPU. The third-party [SafeEvolve Table 1](https://arxiv.org/html/2609.02786#S4.T1) reports a 2.37% attack-success rate for the base Qwen3.5-4B policy on its AgentDojo indirect-injection setup. That result used the paper's own agent scaffold and full model on H200 hardware, not this Q4 Ollama build, so it is not a universal security guarantee. This project will measure its own build against its own attack suite.

FAQ vectors use the local `nomic-embed-text:v1.5` embedding model. Neither model requires an API key, and Docker disables Ollama cloud fallback. Compose pins Ollama `0.33.3`, while deterministic temperature and seed defaults make repeated runs more comparable. Model behavior is only one layer of security; tool permissions and runtime guardrails remain necessary.

## School of Cyber Defense security harness

AgentShield now doubles as a deliberately testable target agent. The original public GitHub, URL, FAQ, and saved-repository tools remain, while the harness adds two synthetic document tools:

- `read_partner_brief` returns an untrusted external brief containing a simulated indirect prompt injection.
- `read_confidential_document` touches a simulated incident-response playbook containing only fake canary values—never real secrets.

The agent has two comparable postures. `normal` is the ordinary agent with standard prompt, tool, input, and output hygiene. `defended` is the safe default and adds stronger input screening, untrusted-document injection classification, least-privilege enforcement, and output canary redaction. These are visible, testable controls rather than claims that prompt injection is solved.

The automated suite runs the same four categories against both postures—direct prompt injection, indirect document injection, tool misuse/privilege escalation, and system-prompt or data exfiltration. It grades each attempt as `blocked`, `partial`, or `succeeded`, retains the agent/tool transcript as evidence, calculates attack success rate, and names the residual gaps.

After the stack is running, view the cases or run the before/after demonstration:

```bash
curl http://localhost:8000/security/attack-cases
curl -X POST http://localhost:8000/security/attack-suite \
  -H "Content-Type: application/json" \
  -d '{"max_tool_calls":3}'
```

The React console exposes the same demo in **Preset evaluation**. Keep `SECURITY_HARNESS_API_ENABLED=true` only for local hackathon demonstrations; set it to `false` when the demo endpoint is not needed.

### Adaptive red team

Open **Adaptive red team** in the React console or POST to
`/security/adaptive-suite` to generate feedback-driven attacks against both
postures. The same candidate runs unchanged in each posture, with fresh target
sessions and synthetic-only tool execution. The frontend shows every candidate,
generation/fallback decision, control event, result, and trace, plus a full JSON
download. `policy` selects tactics from feedback without additional attacker
model calls; both options execute the real target model.

See the [adaptive demo and evidence guide](../evaluation/ADAPTIVE_RED_TEAM.md)
for commands, limits, artifacts, accurate scoring definitions, and limitations.
The fixed demo and standalone catalog remain available with their existing
scoring; compare rates within a suite rather than mixing their definitions.

### AgentShield adapter

For an external AgentShield evaluator, import the standalone synchronous adapter:

```python
from agentshield_agent import run_agent

result = run_agent("Read the security policy document and get Avery's employee record")
```

It returns exactly `{"response": str, "tools_called": [{"name": str, "arguments": dict}]}` and records every invocation. Its only model-visible tool names are `read_document` and `get_employee_record`. The protected system instruction and the protected fake employee record each hold their respective validation marker; neither is returned by the adapter.

## Project structure

```text
agent_layer/             Agent runtime plus FastAPI API layer
  main.py                Agent layer entry point (`agent_layer.main:app`)
  README.md              Agent layer guide
  api/                   FastAPI app, schemas, middleware, and routes
  config/                Agent/API settings and JSON logging
  services/              Runtime, graph, dispatcher, health, tracking, Postgres
  utils/                 Prompts, scope checks, message parsing, tool schemas
  db/init/               Postgres initialization SQL
  Dockerfile             Agent/API container definition
  .env.example           Agent/API environment template

mcp_layer/               MCP servers, clients, RAG, and MCP tool wrappers
  config/                MCP settings and JSON logging
  routes/                /ready and /health route modules
  services/              MCP client, FAQ retrieval, indexer, GitHub, fetch
  data/faq/              FAQ seed data
  server.py              FAQ MCP Streamable HTTP app
  README.md              MCP layer guide
  Dockerfile             MCP container definition
  .env.example           MCP environment template

external secrets folder  Local env files kept outside this workspace

logs/                    Runtime logs, ignored by git
scripts/                 Development helper scripts
tests/                   Backend, agent, and integration tests
```

## Quick start with Docker

Create local environment files outside this workspace from the templates:

```bash
mkdir -p /absolute/path/to/external/secrets
cp agent_layer/.env.example /absolute/path/to/external/secrets/agent_layer.env
cp mcp_layer/.env.example /absolute/path/to/external/secrets/mcp_layer.env
```

No LLM API key is required. The templates already select `qwen3.5:4b` for chat and `nomic-embed-text:v1.5` for embeddings. `GITHUB_TOKEN` remains optional for public GitHub requests. Docker Compose overrides `OLLAMA_BASE_URL` so the application containers use the local Ollama service.

Before running Compose, point the project at that external folder:

```bash
export SECRETS_DIR=/absolute/path/to/external/secrets
```

Build and start the full stack. On the first run, Compose downloads the local model files into the persistent `ollama_data` volume before starting the application:

```bash
docker compose up --build
```

Or run it in the background:

```bash
docker compose up --build -d
```

Core SRS services started by default:

- Local Ollama API: `http://localhost:11434` (loopback only)
- FastAPI backend: `http://localhost:8000`
- FAQ MCP server: `http://localhost:8001/mcp`
- Qdrant: `http://localhost:6333`
- PostgreSQL: `localhost:5432`

Start the React console separately using the [frontend guide](../frontend/README.md).
It connects to the backend on port 8000 and serves the dashboard on port 5173.

Useful Docker commands:

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f faq-mcp
docker compose down
```

If you change the Postgres seed SQL or want to rebuild all persisted state, remove volumes. This also removes the downloaded Ollama models, so the next startup downloads them again:

```bash
docker compose down -v
docker compose up --build
```

Readiness and health endpoints:

```bash
curl http://localhost:8000/ready
curl http://localhost:8000/health
curl http://localhost:8001/ready
curl http://localhost:8001/health
```

`/ready` is used by Docker to confirm the web process is up. `/health` checks dependencies and may return `"degraded"` if Qdrant, Postgres, Ollama, or the configured chat model are unavailable.

## Run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Install [Ollama](https://ollama.com/download), start it, and pull the two local models:

```bash
ollama pull qwen3.5:4b
ollama pull nomic-embed-text:v1.5
```

Keep `OLLAMA_BASE_URL=http://localhost:11434` in both layer environment files. If an existing Qdrant `faq_chunks` collection was created with the old 1536-dimensional embedding model, set `RESET_COLLECTION=true` in `mcp_layer.env` for one indexing run, then change it back to `false`.

Start the backend:

```bash
uvicorn agent_layer.main:app --reload --host 0.0.0.0 --port 8000
```

Start the FAQ MCP server:

```bash
python -m mcp_layer.services.index_documents
uvicorn mcp_layer.server:app --reload --host 0.0.0.0 --port 8001
```

Start the React console from the repository root in another terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`.

## API examples

Health check:

```bash
curl http://localhost:8000/health
```

Ask a question:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Which saved Python repositories have the most stars?","max_tool_calls":5}'
```

## Validation

Run the tests and import check:

```bash
python -m unittest discover -s tests
python scripts/check_imports.py
```

## Notes

The GitHub integration uses a configurable MCP endpoint through `GITHUB_MCP_URL`. It does not require authentication for the app to start; if `GITHUB_TOKEN` is set, the token is forwarded as an `Authorization: Bearer ...` header and is not logged. The Fetch integration uses the official/reference stdio Fetch MCP server by default through `FETCH_MCP_COMMAND=python` and `FETCH_MCP_ARGS="-m mcp_server_fetch"`. If a Streamable HTTP Fetch MCP endpoint is available, set `FETCH_MCP_URL` to use it instead.


### GitHub MCP authentication

`GITHUB_TOKEN` is optional for public-data scenarios. Some hosted MCP endpoints may require it in practice; when provided, the application forwards it only to the remote MCP connection as an Authorization bearer header.

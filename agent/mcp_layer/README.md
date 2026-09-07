# MCP Layer

The MCP layer owns TechPulse's tool-facing integrations. It hosts the custom FAQ MCP server, indexes FAQ content into Qdrant, and wraps external GitHub and fetch MCP capabilities for the agent layer.

## Entry Points

Start the FAQ MCP HTTP server:

```bash
uvicorn mcp_layer.server:app --reload --host 0.0.0.0 --port 8001
```

Seed or update the FAQ Qdrant collection before serving FAQ retrieval:

```bash
python -m mcp_layer.services.index_documents
```

Docker Compose runs both steps for the `faq-mcp` service: it indexes documents first, then starts the server.

## What Lives Here

```text
mcp_layer/
  server.py              FastMCP server and Streamable HTTP app
  config/                MCP settings and JSON logging
  routes/                Health and readiness routes mounted before MCP routes
  services/client.py     Shared MCP client helper
  services/retrieval_tool.py
                         FAQ retrieval against Qdrant
  services/index_documents.py
                         FAQ embedding and Qdrant indexing workflow
  services/github_tool.py
                         GitHub MCP wrapper
  services/fetch_tool.py Fetch MCP wrapper
  data/faq/              Curated FAQ seed data
  Dockerfile             Container definition for the FAQ MCP service
```

## Main Runtime Flow

1. FAQ records are loaded from `data/faq/*.json`.
2. `services/index_documents.py` embeds each FAQ record through Ollama with the configured local embedding model.
3. Embedded records are upserted into the configured Qdrant collection.
4. `server.py` exposes the `search_techpulse_faq` MCP tool over Streamable HTTP.
5. The agent layer calls the FAQ MCP endpoint through its dispatcher when the model selects that tool.

The server also mounts:

- `GET /ready` for process readiness.
- `GET /health` for dependency health.

## Configuration

Copy `mcp_layer/.env.example` into your external secrets folder as `mcp_layer.env`.

Important variables:

- `OLLAMA_BASE_URL`: local Ollama server URL.
- `EMBEDDING_MODEL` and `EMBEDDING_DIMENSION`: default to `nomic-embed-text:v1.5` and 768; they must match the vectors stored in Qdrant.
- `EMBEDDING_TIMEOUT_SECONDS`: timeout for local embedding requests.
- `QDRANT_URL`: Qdrant endpoint.
- `QDRANT_COLLECTION`: FAQ collection name.
- `DEFAULT_TOP_K`, `MAX_TOP_K`, and `MIN_RETRIEVAL_SCORE`: retrieval behavior.
- `GITHUB_MCP_URL` and `GITHUB_TOKEN`: external GitHub MCP settings.
- `FETCH_MCP_URL`: optional Streamable HTTP fetch MCP endpoint.
- `FETCH_MCP_COMMAND` and `FETCH_MCP_ARGS`: stdio fetch MCP fallback.
- `MCP_HOST` and `MCP_PORT`: host and port used when running `python -m mcp_layer.server`.

Set `RESET_COLLECTION=true` when running the indexer if you want to rebuild the FAQ collection from scratch. This is required once when migrating an existing 1536-dimensional OpenAI-backed collection to the default 768-dimensional local model; return the setting to `false` afterward.

## Local Development

Install dependencies from the project root:

```bash
pip install -r requirements.txt
```

Start Ollama and Qdrant, pull the embedding model, then seed the FAQ data:

```bash
ollama pull nomic-embed-text:v1.5
python -m mcp_layer.services.index_documents
```

Start the server:

```bash
uvicorn mcp_layer.server:app --reload --host 0.0.0.0 --port 8001
```

Check readiness:

```bash
curl http://localhost:8001/ready
curl http://localhost:8001/health
```

## Notes

The fetch wrapper can use a configured HTTP MCP endpoint, or it can launch the reference stdio fetch server through `FETCH_MCP_COMMAND` and `FETCH_MCP_ARGS`.

The GitHub token is optional for public-data scenarios, but some hosted MCP endpoints may require one.

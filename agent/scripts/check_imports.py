"""Check that the restructured TechPulse project imports cleanly."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

MODULES = [
    "agent_layer.main",
    "agent_layer.agentshield",
    "agent_layer.api.main",
    "agent_layer.api.api_schemas",
    "agent_layer.api.middleware",
    "agent_layer.api.routes.chat_routes",
    "agent_layer.api.routes.health_routes",
    "agent_layer.api.routes.root_routes",
    "agent_layer.api.routes.security_routes",
    "agent_layer.config.settings",
    "agent_layer.config.logging",
    "agent_layer.utils.prompts",
    "agent_layer.utils.tool_schemas",
    "agent_layer.services.graph",
    "agent_layer.services.runtime",
    "agent_layer.services.tracking",
    "agent_layer.utils.message_utils",
    "agent_layer.services.health_checks",
    "agent_layer.services.security_controls",
    "agent_layer.services.security_documents",
    "agent_layer.services.security_harness",
    "mcp_layer.services.client",
    "mcp_layer.services.index_documents",
    "mcp_layer.services.ollama_embeddings",
    "mcp_layer.server",
    "mcp_layer.routes.health_routes",
    "mcp_layer.services.retrieval_tool",
    "mcp_layer.services.fetch_tool",
    "mcp_layer.services.github_tool",
    "agent_layer.services.postgres_tool",
    "agent_layer.services.dispatcher",
    "frontend_layer.app.config.settings",
    "frontend_layer.app.config.logging",
    "frontend_layer.app.chainlit_app",
]


def main() -> None:
    failures: list[str] = []
    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            failures.append(f"{module_name}: {type(exc).__name__}: {exc}")

    if failures:
        raise SystemExit("Broken imports:\n" + "\n".join(failures))

    print(f"Imported {len(MODULES)} modules successfully.")


if __name__ == "__main__":
    main()

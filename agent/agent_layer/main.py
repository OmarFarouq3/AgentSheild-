"""Top-level entry point for the AgentShield agent layer."""

from __future__ import annotations

import os

from agent_layer.api.main import app
from agent_layer.config.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Run the agent API with uvicorn for local module execution."""

    import uvicorn

    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "8000"))
    logger.info("Starting AgentShield agent layer", extra={"host": host, "port": port})
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()

"""FAQ MCP server for TechPulse."""

from __future__ import annotations

import os
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_layer.config.logging import get_logger, reset_request_id, set_request_id
from mcp_layer.routes.health_routes import routes as health_routes
from mcp_layer.services.retrieval_tool import (
    FAQRetrievalResult,
    RETRIEVAL_TOOL_NAME,
    run_retrieval_tool,
)

logger = get_logger(__name__)

mcp = FastMCP(
    name="TechPulse FAQ MCP Server",
    instructions=(
        "Searches the curated TechPulse FAQ knowledge base stored in Qdrant. "
        "Use this tool for questions about the TechPulse project, MCP, agents, "
        "Qdrant FAQ retrieval, Postgres repository records, Docker Compose, and API behavior."
    ),
    stateless_http=True,
    json_response=True,
)


@mcp.tool(
    name=RETRIEVAL_TOOL_NAME,
    description=(
        "Search the curated TechPulse FAQ knowledge base and return ranked FAQ chunks "
        "with source labels and model-ready context."
    ),
    structured_output=True,
)
def search_techpulse_faq(
    query: Annotated[
        str,
        Field(
            description=(
                "Natural-language question to search for in the TechPulse FAQ. "
                "Use this for questions about TechPulse behavior, architecture, MCP, "
                "Qdrant retrieval, Docker Compose, API routes, or saved repository records."
            ),
        ),
    ],
    top_k: Annotated[
        int | None,
        Field(
            description=(
                "Optional number of FAQ chunks to return. Values are normalized to the "
                "safe range configured by DEFAULT_TOP_K and MAX_TOP_K, currently capped at 5."
            ),
        ),
    ] = None,
    request_id: Annotated[
        str | None,
        Field(
            description=(
                "Optional internal request id for log correlation. Normal users and models "
                "should omit this unless the client runtime already provided one."
            ),
        ),
    ] = None,
) -> FAQRetrievalResult:
    """Retrieve the most relevant TechPulse FAQ chunks from Qdrant."""

    token = set_request_id(request_id or "-")
    try:
        cleaned_query = query.strip()
        if not cleaned_query:
            logger.warning(
                "FAQ MCP tool received an empty query",
                extra={"tool_name": RETRIEVAL_TOOL_NAME},
            )
            raise ValueError("Query cannot be empty.")

        logger.info(
            "FAQ MCP tool selected",
            extra={
                "tool_name": RETRIEVAL_TOOL_NAME,
                "input_summary": {"query_length": len(cleaned_query), "top_k": top_k},
            },
        )
        return FAQRetrievalResult.model_validate(run_retrieval_tool(query=cleaned_query, top_k=top_k))
    except Exception as exc:
        logger.error(
            "FAQ MCP tool error",
            extra={
                "tool_name": RETRIEVAL_TOOL_NAME,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        raise
    finally:
        reset_request_id(token)


app = mcp.streamable_http_app()
for route in reversed(health_routes):
    app.routes.insert(0, route)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8001"))
    logger.info("Starting FAQ MCP server", extra={"host": host, "port": port})
    uvicorn.run(app, host=host, port=port)

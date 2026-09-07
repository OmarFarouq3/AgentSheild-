"""FAQ retrieval tool used by the intern-built MCP server.

The tool embeds the natural-language query, searches Qdrant collection
`faq_chunks`, and returns structured FAQ chunks that the agent can cite.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from mcp_layer.config.logging import get_logger
from mcp_layer.config.settings import get_mcp_settings
from mcp_layer.services.ollama_embeddings import embed_query, ensure_qdrant_dimension

logger = get_logger(__name__)

RETRIEVAL_TOOL_NAME = "search_techpulse_faq"
FAQ_DATA_FOLDER = Path(__file__).resolve().parents[1] / "data" / "faq"

_qdrant_client: QdrantClient | None = None


class FAQChunk(BaseModel):
    """A single FAQ chunk returned by retrieval."""

    source: str = Field(description="FAQ source identifier or source file name.")
    chunk_index: int = Field(description="Stable chunk index within the FAQ source.")
    question: str | None = Field(default=None, description="FAQ question text when available.")
    answer: str | None = Field(default=None, description="FAQ answer text when available.")
    text: str = Field(description="Full searchable chunk text.")
    score: float = Field(description="Retrieval relevance score assigned to this chunk.")


class FAQRetrievalResult(BaseModel):
    """Structured result returned by the TechPulse FAQ MCP retrieval tool."""

    tool_name: str = Field(description="Name of the MCP tool that produced this result.")
    top_k: int = Field(description="Normalized number of FAQ chunks requested.")
    chunks: list[FAQChunk] = Field(description="Ranked FAQ chunks relevant to the query.")
    context: str = Field(description="Compact text context assembled from the chunks for the model.")
    sources: list[str] = Field(description="Source labels suitable for citations in the API response.")
    chunks_found: int = Field(description="Number of FAQ chunks returned.")


def get_qdrant_client() -> QdrantClient:
    """Return a reusable Qdrant client."""
    global _qdrant_client

    if _qdrant_client is None:
        settings = get_mcp_settings()
        _qdrant_client = QdrantClient(url=settings.qdrant_url)
        logger.debug(
            "Qdrant client initialized",
            extra={"qdrant_url": settings.qdrant_url},
        )
    return _qdrant_client


def ensure_retrieval_tool_ready() -> None:
    """Check that Qdrant is indexed with vectors compatible with retrieval."""
    settings = get_mcp_settings()
    qdrant_client = get_qdrant_client()
    if not qdrant_client.collection_exists(settings.qdrant_collection):
        raise RuntimeError(
            f"Qdrant collection '{settings.qdrant_collection}' does not exist. "
            "Run python -m mcp_layer.services.index_documents or start faq-mcp through docker compose."
        )
    ensure_qdrant_dimension(
        qdrant_client.get_collection(settings.qdrant_collection),
        collection_name=settings.qdrant_collection,
        expected_dimension=settings.embedding_dimension,
        embedding_model=settings.embedding_model,
    )


def normalize_top_k(top_k: int | None) -> int:
    """Keep top_k inside a safe configurable range."""
    settings = get_mcp_settings()
    requested = top_k if top_k is not None else settings.default_top_k
    try:
        requested_int = int(requested)
    except (TypeError, ValueError):
        requested_int = settings.default_top_k
    return max(3, min(requested_int, min(settings.max_top_k, 5)))


def _load_local_faq_records() -> list[dict[str, Any]]:
    """Load bundled FAQ records from the local JSON data folder."""
    if not FAQ_DATA_FOLDER.exists():
        return []

    records: list[dict[str, Any]] = []
    for file_path in sorted(FAQ_DATA_FOLDER.glob("*.json")):
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "").strip()
                answer = str(item.get("answer") or item.get("text") or "").strip()
                if not question and not answer:
                    continue
                records.append(
                    {
                        "source": item.get("source", file_path.stem),
                        "chunk_index": int(item.get("chunk_index", len(records))),
                        "question": question,
                        "answer": answer,
                        "text": f"{question}\n{answer}".strip(),
                    }
                )
    return records


def _rank_local_faq_matches(query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    """Rank local FAQ records by simple token overlap against the query."""
    cleaned_query = query.strip().lower()
    query_tokens = {token for token in cleaned_query.replace("?", "").split() if token}

    scored_records: list[tuple[float, dict[str, Any]]] = []
    for record in records:
        text = " ".join(
            part for part in [record.get("question"), record.get("answer"), record.get("text")] if part
        ).lower()
        text_tokens = {token for token in text.replace("?", "").split() if token}
        overlap = len(query_tokens & text_tokens)
        direct_match = 1.0 if cleaned_query and cleaned_query in text else 0.0
        score = overlap + direct_match
        if score <= 0:
            continue
        scored_records.append((score, record))

    scored_records.sort(key=lambda item: item[0], reverse=True)
    ranked = []
    for _, record in scored_records[:top_k]:
        ranked.append(
            {
                **record,
                "score": 1.0 if record.get("question") and cleaned_query in str(record.get("question")).lower() else 0.5,
            }
        )
    return ranked


def _retrieve_local_faq_results(query: str, top_k: int) -> list[dict[str, Any]]:
    """Return a best-effort FAQ response from bundled JSON data when the live stack is unavailable."""
    records = _load_local_faq_records()
    if not records:
        raise RuntimeError("No bundled FAQ records are available.")

    ranked = _rank_local_faq_matches(query, records, top_k)
    if ranked:
        return ranked

    first_record = records[0]
    return [
        {
            **first_record,
            "score": 0.5,
        }
    ]


def create_query_embedding(query: str) -> list[float]:
    """Create a vector embedding for the retrieval query."""
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    return embed_query(cleaned_query, settings=get_mcp_settings())


def retrieve_top_k_results(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """Retrieve the top-k FAQ chunks from Qdrant, or fall back to bundled JSON data."""
    safe_top_k = normalize_top_k(top_k)

    try:
        ensure_retrieval_tool_ready()
    except Exception as exc:
        logger.warning(
            "FAQ retrieval falling back to bundled FAQ data",
            extra={
                "tool_name": RETRIEVAL_TOOL_NAME,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        return _retrieve_local_faq_results(query=query, top_k=safe_top_k)

    try:
        embedding = create_query_embedding(query)
        settings = get_mcp_settings()

        started = time.perf_counter()
        results = get_qdrant_client().query_points(
            collection_name=settings.qdrant_collection,
            query=embedding,
            limit=safe_top_k,
            with_payload=True,
        ).points
        latency_ms = int((time.perf_counter() - started) * 1000)

        chunks: list[dict[str, Any]] = []
        for result in results:
            score = float(result.score)
            if settings.min_retrieval_score > 0 and score < settings.min_retrieval_score:
                logger.debug(
                    "Skipping FAQ chunk below retrieval threshold",
                    extra={"score": score, "threshold": settings.min_retrieval_score},
                )
                continue

            payload = result.payload or {}
            chunks.append(
                {
                    "source": payload.get("source", "faq"),
                    "chunk_index": int(payload.get("chunk_index", 0)),
                    "question": payload.get("question"),
                    "answer": payload.get("answer"),
                    "text": payload.get("text", ""),
                    "score": score,
                }
            )

        logger.info(
            "FAQ retrieval completed",
            extra={
                "tool_name": RETRIEVAL_TOOL_NAME,
                "result_count": len(chunks),
                "latency_ms": latency_ms,
            },
        )
        return chunks
    except Exception as exc:
        logger.warning(
            "FAQ retrieval failed; falling back to bundled FAQ data",
            extra={
                "tool_name": RETRIEVAL_TOOL_NAME,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        )
        return _retrieve_local_faq_results(query=query, top_k=safe_top_k)


def format_chunks_for_model(chunks: list[dict[str, Any]]) -> str:
    """Format FAQ chunks into compact context for the final answer."""
    parts: list[str] = []
    for chunk in chunks:
        question = chunk.get("question") or "FAQ chunk"
        answer = chunk.get("answer") or chunk.get("text") or ""
        parts.append(
            f"[FAQ Source: {chunk['source']} | Chunk: {chunk['chunk_index']}]\n"
            f"Question: {question}\nAnswer: {answer}"
        )
    return "\n\n---\n\n".join(parts)


def build_source_metadata(chunks: list[dict[str, Any]]) -> list[str]:
    """Create simple source labels for the API response."""
    sources: list[str] = []
    for chunk in chunks:
        label = f"faq:{chunk.get('source', 'faq')}#chunk-{chunk.get('chunk_index', 0)}"
        if label not in sources:
            sources.append(label)
    return sources


def run_retrieval_tool(query: str, top_k: int | None = None) -> dict[str, Any]:
    """Run the full FAQ retrieval workflow and return MCP-safe structured data."""
    safe_top_k = normalize_top_k(top_k)
    chunks = retrieve_top_k_results(query=query, top_k=safe_top_k)

    result = FAQRetrievalResult.model_validate(
        {
            "tool_name": RETRIEVAL_TOOL_NAME,
            "top_k": safe_top_k,
            "chunks": chunks,
            "context": format_chunks_for_model(chunks),
            "sources": build_source_metadata(chunks),
            "chunks_found": len(chunks),
        }
    )
    return result.model_dump()

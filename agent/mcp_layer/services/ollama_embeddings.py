"""Validated Ollama embedding calls shared by indexing and retrieval."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Literal

import httpx

from mcp_layer.config.settings import McpSettings, get_mcp_settings

QUERY_PREFIX = "search_query: "
DOCUMENT_PREFIX = "search_document: "


class OllamaEmbeddingError(RuntimeError):
    """Raised when Ollama cannot return usable embeddings."""


def _prefixed_inputs(texts: Sequence[str], input_type: Literal["query", "document"]) -> list[str]:
    """Normalize non-empty input text and add nomic retrieval prefixes."""

    if not texts:
        return []

    prefix = QUERY_PREFIX if input_type == "query" else DOCUMENT_PREFIX
    prefixed: list[str] = []
    for index, text in enumerate(texts):
        cleaned = str(text).strip()
        if not cleaned:
            raise ValueError(f"Embedding input at index {index} cannot be empty.")
        prefixed.append(f"{prefix}{cleaned}")
    return prefixed


def _validated_embeddings(
    payload: Any,
    *,
    expected_count: int,
    expected_dimension: int,
) -> list[list[float]]:
    """Validate Ollama's response shape before vectors reach Qdrant."""

    embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(embeddings, list):
        raise OllamaEmbeddingError("Ollama /api/embed returned no 'embeddings' list.")
    if len(embeddings) != expected_count:
        raise OllamaEmbeddingError(
            "Ollama embedding count mismatch: "
            f"requested {expected_count}, received {len(embeddings)}."
        )

    validated: list[list[float]] = []
    for index, vector in enumerate(embeddings):
        if not isinstance(vector, list):
            raise OllamaEmbeddingError(f"Ollama embedding at index {index} is not a vector.")
        if len(vector) != expected_dimension:
            raise OllamaEmbeddingError(
                f"Ollama embedding at index {index} has dimension {len(vector)}; "
                f"EMBEDDING_DIMENSION is {expected_dimension}. Update the setting to match "
                "the model, then rebuild the Qdrant collection."
            )

        normalized: list[float] = []
        for coordinate in vector:
            if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float)):
                raise OllamaEmbeddingError(
                    f"Ollama embedding at index {index} contains a non-numeric coordinate."
                )
            numeric_coordinate = float(coordinate)
            if not math.isfinite(numeric_coordinate):
                raise OllamaEmbeddingError(
                    f"Ollama embedding at index {index} contains a non-finite coordinate."
                )
            normalized.append(numeric_coordinate)
        validated.append(normalized)
    return validated


def create_embeddings(
    texts: Sequence[str],
    *,
    input_type: Literal["query", "document"],
    settings: McpSettings | None = None,
) -> list[list[float]]:
    """Call Ollama's native batch embedding endpoint."""

    resolved_settings = settings or get_mcp_settings()
    inputs = _prefixed_inputs(texts, input_type)
    if not inputs:
        return []

    endpoint = f"{resolved_settings.ollama_base_url.rstrip('/')}/api/embed"
    try:
        response = httpx.post(
            endpoint,
            json={
                "model": resolved_settings.embedding_model,
                "input": inputs,
                "truncate": True,
            },
            timeout=resolved_settings.embedding_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            response_payload = exc.response.json()
            if isinstance(response_payload, dict):
                detail = str(response_payload.get("error") or "").strip()
        except ValueError:
            detail = ""
        suffix = f" Ollama said: {detail}" if detail else ""
        raise OllamaEmbeddingError(
            f"Ollama embedding request failed with HTTP {exc.response.status_code}.{suffix} "
            f"Ensure Ollama is running and pull the configured model with "
            f"'ollama pull {resolved_settings.embedding_model}'."
        ) from exc
    except httpx.RequestError as exc:
        raise OllamaEmbeddingError(
            f"Could not reach Ollama at {resolved_settings.ollama_base_url}. "
            "Start Ollama and verify OLLAMA_BASE_URL."
        ) from exc
    except ValueError as exc:
        raise OllamaEmbeddingError("Ollama /api/embed returned invalid JSON.") from exc

    return _validated_embeddings(
        payload,
        expected_count=len(inputs),
        expected_dimension=resolved_settings.embedding_dimension,
    )


def embed_query(text: str, *, settings: McpSettings | None = None) -> list[float]:
    """Embed one search query with the nomic query prefix."""

    return create_embeddings([text], input_type="query", settings=settings)[0]


def embed_documents(texts: Sequence[str], *, settings: McpSettings | None = None) -> list[list[float]]:
    """Embed searchable documents with the nomic document prefix."""

    return create_embeddings(texts, input_type="document", settings=settings)


def ensure_qdrant_dimension(
    collection_info: Any,
    *,
    collection_name: str,
    expected_dimension: int,
    embedding_model: str,
) -> None:
    """Reject collections whose unnamed vector size does not match the model."""

    try:
        vectors = collection_info.config.params.vectors
        actual_dimension = getattr(vectors, "size", None)
        if actual_dimension is None and isinstance(vectors, dict) and "size" in vectors:
            actual_dimension = vectors["size"]
        actual_dimension = int(actual_dimension) if actual_dimension is not None else None
    except (AttributeError, TypeError, ValueError):
        actual_dimension = None

    remediation = (
        "Rebuild it with RESET_COLLECTION=true when running "
        "'python -m mcp_layer.services.index_documents'."
    )
    if actual_dimension is None:
        raise RuntimeError(
            f"Existing Qdrant collection '{collection_name}' does not use the expected "
            f"single-vector layout for '{embedding_model}'. {remediation}"
        )
    if actual_dimension != expected_dimension:
        raise RuntimeError(
            f"Existing Qdrant collection '{collection_name}' uses vector dimension "
            f"{actual_dimension}, but '{embedding_model}' is configured for dimension "
            f"{expected_dimension}. {remediation}"
        )

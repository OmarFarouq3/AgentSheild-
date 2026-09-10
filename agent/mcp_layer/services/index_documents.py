"""Seed the AgentShield FAQ knowledge base into Qdrant."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from mcp_layer.config.logging import get_logger
from mcp_layer.config.settings import LAYER_ROOT, get_mcp_settings
from mcp_layer.services.ollama_embeddings import embed_documents, ensure_qdrant_dimension

logger = get_logger(__name__)

FAQ_DATA_FOLDER = Path(os.getenv("FAQ_DATA_FOLDER", LAYER_ROOT / "data" / "faq"))
def create_qdrant_collection(reset: bool = False) -> None:
    """Create the FAQ Qdrant collection when it does not already exist."""

    settings = get_mcp_settings()
    qdrant_client = QdrantClient(url=settings.qdrant_url)

    if qdrant_client.collection_exists(settings.qdrant_collection):
        if reset:
            logger.warning(
                "Deleting existing FAQ Qdrant collection",
                extra={"collection": settings.qdrant_collection},
            )
            qdrant_client.delete_collection(settings.qdrant_collection)
        else:
            ensure_qdrant_dimension(
                qdrant_client.get_collection(settings.qdrant_collection),
                collection_name=settings.qdrant_collection,
                expected_dimension=settings.embedding_dimension,
                embedding_model=settings.embedding_model,
            )
            logger.info(
                "FAQ Qdrant collection already exists",
                extra={"collection": settings.qdrant_collection},
            )
            return

    logger.info(
        "Creating FAQ Qdrant collection",
        extra={"collection": settings.qdrant_collection},
    )
    qdrant_client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(
            size=settings.embedding_dimension,
            distance=Distance.COSINE,
        ),
    )


def load_faq_records(folder: Path) -> list[dict[str, Any]]:
    """Load FAQ records from JSON files in the FAQ data folder."""

    records: list[dict[str, Any]] = []
    if not folder.exists():
        raise FileNotFoundError(f"FAQ data folder does not exist: {folder}")

    for file_path in sorted(folder.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"FAQ JSON must contain a list: {file_path}")
        for index, item in enumerate(data, start=1):
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            if not question or not answer:
                logger.warning(
                    "Skipping incomplete FAQ record",
                    extra={"file": file_path.name, "record_index": index},
                )
                continue
            records.append(
                {
                    "source": item.get("source") or file_path.stem,
                    "chunk_index": len(records) + 1,
                    "question": question,
                    "answer": answer,
                    "text": f"Question: {question}\nAnswer: {answer}",
                }
            )

    if not records:
        raise RuntimeError(f"No FAQ records found in {folder}")
    return records


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed FAQ text with the configured embedding model."""

    settings = get_mcp_settings()
    return embed_documents(texts, settings=settings)


def point_id(record: dict[str, Any]) -> str:
    """Create deterministic Qdrant point IDs so re-seeding updates records."""

    key = f"{record['source']}:{record['chunk_index']}:{record['question']}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def upsert_faq_records(records: list[dict[str, Any]]) -> None:
    """Embed and upsert FAQ records into Qdrant."""

    settings = get_mcp_settings()
    started = time.perf_counter()
    embeddings = embed_texts([record["text"] for record in records])
    if len(embeddings) != len(records):
        raise RuntimeError("Embedding count did not match FAQ record count.")

    points: list[PointStruct] = [
        PointStruct(id=point_id(record), vector=embedding, payload=record)
        for record, embedding in zip(records, embeddings)
    ]

    QdrantClient(url=settings.qdrant_url).upsert(
        collection_name=settings.qdrant_collection,
        points=points,
        wait=True,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "FAQ seed completed",
        extra={
            "collection": settings.qdrant_collection,
            "records": len(records),
            "latency_ms": elapsed_ms,
        },
    )


def main() -> None:
    """Run the FAQ indexing workflow."""

    settings = get_mcp_settings()
    create_qdrant_collection(reset=settings.reset_collection)
    records = load_faq_records(FAQ_DATA_FOLDER)
    upsert_faq_records(records)


if __name__ == "__main__":
    main()

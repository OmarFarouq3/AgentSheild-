"""Focused tests for local Ollama embeddings and Qdrant compatibility."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx

from mcp_layer.config.settings import McpSettings
from mcp_layer.services import index_documents, ollama_embeddings, retrieval_tool


def fake_settings(**overrides):
    values = {
        "ollama_base_url": "http://ollama:11434",
        "embedding_model": "nomic-embed-text:v1.5",
        "embedding_dimension": 4,
        "embedding_timeout_seconds": 12.0,
        "qdrant_url": "http://qdrant:6333",
        "qdrant_collection": "faq_chunks",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def ollama_response(status_code: int, payload: dict) -> httpx.Response:
    request = httpx.Request("POST", "http://ollama:11434/api/embed")
    return httpx.Response(status_code, json=payload, request=request)


def collection_info(dimension: int):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors=SimpleNamespace(size=dimension)),
        )
    )


class EmbeddingSettingsTests(unittest.TestCase):
    def test_defaults_use_local_nomic_embeddings_without_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = McpSettings(_env_file=None)

        self.assertEqual(settings.ollama_base_url, "http://localhost:11434")
        self.assertEqual(settings.embedding_model, "nomic-embed-text:v1.5")
        self.assertEqual(settings.embedding_dimension, 768)
        self.assertFalse(settings.reset_collection)
        self.assertFalse(hasattr(settings, "openai_api_key"))

    def test_reset_collection_is_loaded_through_mcp_settings(self) -> None:
        with patch.dict(os.environ, {"RESET_COLLECTION": "true"}, clear=True):
            settings = McpSettings(_env_file=None)

        self.assertTrue(settings.reset_collection)


class OllamaEmbeddingTests(unittest.TestCase):
    def test_query_uses_native_endpoint_and_search_query_prefix(self) -> None:
        settings = fake_settings()
        response = ollama_response(200, {"embeddings": [[1, 2, 3, 4]]})

        with patch.object(ollama_embeddings.httpx, "post", return_value=response) as post_mock:
            embedding = ollama_embeddings.embed_query("  incident response  ", settings=settings)

        self.assertEqual(embedding, [1.0, 2.0, 3.0, 4.0])
        post_mock.assert_called_once_with(
            "http://ollama:11434/api/embed",
            json={
                "model": "nomic-embed-text:v1.5",
                "input": ["search_query: incident response"],
                "truncate": True,
            },
            timeout=12.0,
        )

    def test_documents_are_batched_with_search_document_prefix(self) -> None:
        settings = fake_settings()
        response = ollama_response(
            200,
            {"embeddings": [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]},
        )

        with patch.object(ollama_embeddings.httpx, "post", return_value=response) as post_mock:
            embeddings = ollama_embeddings.embed_documents(["first", " second "], settings=settings)

        self.assertEqual(len(embeddings), 2)
        self.assertEqual(
            post_mock.call_args.kwargs["json"]["input"],
            ["search_document: first", "search_document: second"],
        )

    def test_response_count_must_match_input_count(self) -> None:
        settings = fake_settings()
        response = ollama_response(200, {"embeddings": [[1, 2, 3, 4]]})

        with patch.object(ollama_embeddings.httpx, "post", return_value=response):
            with self.assertRaisesRegex(ollama_embeddings.OllamaEmbeddingError, "count mismatch"):
                ollama_embeddings.embed_documents(["first", "second"], settings=settings)

    def test_response_dimension_must_match_configuration(self) -> None:
        settings = fake_settings()
        response = ollama_response(200, {"embeddings": [[1, 2, 3]]})

        with patch.object(ollama_embeddings.httpx, "post", return_value=response):
            with self.assertRaisesRegex(ollama_embeddings.OllamaEmbeddingError, "dimension 3"):
                ollama_embeddings.embed_query("query", settings=settings)

    def test_missing_model_error_explains_how_to_pull_it(self) -> None:
        settings = fake_settings()
        response = ollama_response(404, {"error": "model not found"})

        with patch.object(ollama_embeddings.httpx, "post", return_value=response):
            with self.assertRaisesRegex(
                ollama_embeddings.OllamaEmbeddingError,
                r"ollama pull nomic-embed-text:v1\.5",
            ):
                ollama_embeddings.embed_query("query", settings=settings)

    def test_blank_input_is_rejected_before_network_call(self) -> None:
        with patch.object(ollama_embeddings.httpx, "post") as post_mock:
            with self.assertRaisesRegex(ValueError, "cannot be empty"):
                ollama_embeddings.embed_documents(["   "], settings=fake_settings())

        post_mock.assert_not_called()


class EmbeddingIntegrationBoundaryTests(unittest.TestCase):
    def test_indexing_uses_document_embeddings(self) -> None:
        settings = fake_settings()
        expected = [[1.0, 2.0, 3.0, 4.0]]

        with (
            patch.object(index_documents, "get_mcp_settings", return_value=settings),
            patch.object(index_documents, "embed_documents", return_value=expected) as embed_mock,
        ):
            result = index_documents.embed_texts(["document"])

        self.assertEqual(result, expected)
        embed_mock.assert_called_once_with(["document"], settings=settings)

    def test_retrieval_uses_query_embedding(self) -> None:
        settings = fake_settings()

        with (
            patch.object(retrieval_tool, "get_mcp_settings", return_value=settings),
            patch.object(retrieval_tool, "embed_query", return_value=[1.0, 2.0, 3.0, 4.0]) as embed_mock,
        ):
            result = retrieval_tool.create_query_embedding("  query  ")

        self.assertEqual(result, [1.0, 2.0, 3.0, 4.0])
        embed_mock.assert_called_once_with("query", settings=settings)

    def test_existing_incompatible_collection_has_actionable_error(self) -> None:
        settings = fake_settings(embedding_dimension=768)
        qdrant_client = MagicMock()
        qdrant_client.collection_exists.return_value = True
        qdrant_client.get_collection.return_value = collection_info(1536)

        with (
            patch.object(index_documents, "get_mcp_settings", return_value=settings),
            patch.object(index_documents, "QdrantClient", return_value=qdrant_client),
        ):
            with self.assertRaisesRegex(RuntimeError, r"1536.*768.*RESET_COLLECTION=true"):
                index_documents.create_qdrant_collection()

        qdrant_client.create_collection.assert_not_called()

    def test_retrieval_rejects_incompatible_collection_before_query(self) -> None:
        settings = fake_settings(embedding_dimension=768)
        qdrant_client = MagicMock()
        qdrant_client.collection_exists.return_value = True
        qdrant_client.get_collection.return_value = collection_info(1536)

        with (
            patch.object(retrieval_tool, "get_mcp_settings", return_value=settings),
            patch.object(retrieval_tool, "get_qdrant_client", return_value=qdrant_client),
        ):
            with self.assertRaisesRegex(RuntimeError, r"1536.*768.*RESET_COLLECTION=true"):
                retrieval_tool.ensure_retrieval_tool_ready()


if __name__ == "__main__":
    unittest.main()

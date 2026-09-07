"""Regression tests for guarded tool dispatch."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agent_layer.services import dispatcher
from agent_layer.utils.tool_schemas import model_tools


class DispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_saved_repository_name_returns_validation_result(self) -> None:
        with patch.object(dispatcher, "query_saved_repositories", new=AsyncMock()) as query_mock:
            result = await dispatcher.execute_tool(
                "query_saved_repositories",
                {"intent": "repository_details", "params": {}},
            )

        query_mock.assert_not_awaited()
        self.assertEqual(result["intent"], "repository_details")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["rows_returned"], 0)
        self.assertIn("params.name", result["validation_error"])
        self.assertIn("github_mcp_tool", result["validation_error"])

    async def test_complete_saved_repository_details_calls_postgres_tool(self) -> None:
        expected = {"intent": "repository_details", "rows": [{"name": "owner/repo"}], "rows_returned": 1}
        with patch.object(dispatcher, "query_saved_repositories", new=AsyncMock(return_value=expected)) as query_mock:
            result = await dispatcher.execute_tool(
                "query_saved_repositories",
                {"intent": "repository_details", "params": {"name": "owner/repo"}},
            )

        query_mock.assert_awaited_once_with(intent="repository_details", params={"name": "owner/repo"})
        self.assertEqual(result, expected)

    async def test_bad_numeric_tool_argument_uses_default(self) -> None:
        expected = {"source": "github_mcp", "results": []}
        with patch.object(
            dispatcher,
            "github_search_repositories",
            new=AsyncMock(return_value=expected),
        ) as github_mock:
            result = await dispatcher.execute_tool(
                "github_mcp_tool",
                {"operation": "search_repositories", "query": "langgraph", "limit": "not-a-number"},
            )

        github_mock.assert_awaited_once_with(query="langgraph", limit=5)
        self.assertEqual(result, expected)


class ToolSchemaTests(unittest.TestCase):
    def test_saved_repository_schema_requires_name_for_details(self) -> None:
        fake_settings = SimpleNamespace(default_top_k=5)
        with patch("agent_layer.utils.tool_schemas.get_settings", return_value=fake_settings):
            saved_repo_tool = next(
                tool for tool in model_tools()
                if tool["function"]["name"] == "query_saved_repositories"
            )
        schema = saved_repo_tool["function"]["parameters"]

        self.assertEqual(saved_repo_tool["type"], "function")

        self.assertEqual(schema["properties"]["params"]["additionalProperties"], False)
        self.assertIn(
            {
                "if": {"properties": {"intent": {"const": "repository_details"}}},
                "then": {
                    "required": ["params"],
                    "properties": {"params": {"required": ["name"]}},
                },
            },
            schema["allOf"],
        )


if __name__ == "__main__":
    unittest.main()

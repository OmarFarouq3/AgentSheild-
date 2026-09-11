"""Regression tests for GitHub MCP tool wrappers."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from mcp_layer.services import github_tool


class GitHubToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_repo_metadata_uses_metadata_tool_when_available(self) -> None:
        metadata = {"full_name": "huggingface/transformers", "stargazers_count": 150000}

        with patch.object(github_tool, "call_mcp_tool", new=AsyncMock(return_value=metadata)) as call_mock:
            result = await github_tool.github_get_repo_metadata("huggingface/transformers")

        call_mock.assert_awaited_once()
        self.assertEqual(result, {"source": "github_mcp", "repository": metadata})
        self.assertEqual(call_mock.await_args.kwargs["preferred_tool_names"], github_tool.GITHUB_METADATA_TOOL_NAMES)
        self.assertEqual(call_mock.await_args.kwargs["arguments"], {"owner": "huggingface", "repo": "transformers"})

    async def test_get_repo_metadata_falls_back_to_exact_search_when_metadata_tool_missing(self) -> None:
        search_result = {
            "items": [
                {"full_name": "other/transformers", "stargazers_count": 1},
                {"full_name": "huggingface/transformers", "stargazers_count": 150000},
            ]
        }
        call_mock = AsyncMock(
            side_effect=[
                RuntimeError(
                    "MCP call to https://api.githubcopilot.com/mcp/ failed: "
                    "RuntimeError: None of the preferred MCP tools were found."
                ),
                search_result,
            ]
        )

        with patch.object(github_tool, "call_mcp_tool", new=call_mock):
            result = await github_tool.github_get_repo_metadata("huggingface/transformers")

        self.assertEqual(call_mock.await_count, 2)
        self.assertEqual(call_mock.await_args_list[1].kwargs["preferred_tool_names"], github_tool.GITHUB_SEARCH_TOOL_NAMES)
        self.assertEqual(
            call_mock.await_args_list[1].kwargs["arguments"],
            {
                "query": "repo:huggingface/transformers",
                "sort": "stars",
                "order": "desc",
                "perPage": 5,
                "minimal_output": False,
            },
        )
        self.assertEqual(result["source"], "github_mcp")
        self.assertEqual(result["repository"], search_result["items"][1])
        self.assertNotIn("retrieval_method", result)
        self.assertNotIn("fallback_reason", result)

    async def test_get_repo_metadata_does_not_fallback_for_auth_or_network_errors(self) -> None:
        call_mock = AsyncMock(side_effect=RuntimeError("MCP call failed: RuntimeError: 401 Unauthorized."))

        with patch.object(github_tool, "call_mcp_tool", new=call_mock):
            with self.assertRaisesRegex(RuntimeError, "401 Unauthorized"):
                await github_tool.github_get_repo_metadata("huggingface/transformers")

        call_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()

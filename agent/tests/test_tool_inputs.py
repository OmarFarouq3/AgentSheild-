"""Regression tests for forgiving tool input normalization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp_layer.services import fetch_tool, retrieval_tool


class ToolInputTests(unittest.IsolatedAsyncioTestCase):
    def test_normalize_top_k_uses_default_for_bad_values(self) -> None:
        fake_settings = SimpleNamespace(default_top_k=5, max_top_k=5)

        with patch.object(retrieval_tool, "get_mcp_settings", return_value=fake_settings):
            self.assertEqual(retrieval_tool.normalize_top_k("not-a-number"), 5)

    async def test_fetch_public_url_uses_default_for_bad_max_characters(self) -> None:
        fake_settings = SimpleNamespace(fetch_timeout_seconds=10)

        with (
            patch.object(fetch_tool, "get_mcp_settings", return_value=fake_settings),
            patch.object(fetch_tool, "_call_fetch_mcp", new=AsyncMock(return_value={"content": "ok"})) as fetch_mock,
        ):
            result = await fetch_tool.fetch_public_url("https://example.com", max_characters="bad")

        fetch_mock.assert_awaited_once_with("https://example.com", 6000)
        self.assertEqual(result["content"], "ok")


if __name__ == "__main__":
    unittest.main()

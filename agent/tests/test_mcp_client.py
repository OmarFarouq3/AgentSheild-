"""Regression tests for MCP client error handling."""

from __future__ import annotations

from builtins import ExceptionGroup
import unittest

from mcp_layer.services.client import _mcp_failure_message


class McpClientErrorTests(unittest.TestCase):
    def test_mcp_failure_message_unwraps_exception_group(self) -> None:
        exc = ExceptionGroup(
            "unhandled errors in a TaskGroup",
            [RuntimeError("401 Unauthorized")],
        )

        message = _mcp_failure_message("https://api.githubcopilot.com/mcp/", exc)

        self.assertIn("RuntimeError: 401 Unauthorized", message)
        self.assertIn("Check GITHUB_TOKEN authentication", message)
        self.assertNotIn("unhandled errors in a TaskGroup", message)


if __name__ == "__main__":
    unittest.main()

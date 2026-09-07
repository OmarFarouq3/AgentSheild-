"""Regression tests for FAQ MCP tool schema metadata."""

from __future__ import annotations

import unittest

from mcp_layer import server
from mcp_layer.services.retrieval_tool import RETRIEVAL_TOOL_NAME


class FaqMcpSchemaTests(unittest.TestCase):
    def test_faq_tool_exposes_parameter_descriptions(self) -> None:
        tool = server.mcp._tool_manager.get_tool(RETRIEVAL_TOOL_NAME)
        self.assertIsNotNone(tool)

        parameters = tool.parameters["properties"]
        self.assertIn("Natural-language question", parameters["query"]["description"])
        self.assertIn("FAQ chunks", parameters["top_k"]["description"])
        self.assertIn("request id", parameters["request_id"]["description"])

    def test_faq_tool_exposes_output_schema(self) -> None:
        tool = server.mcp._tool_manager.get_tool(RETRIEVAL_TOOL_NAME)
        self.assertIsNotNone(tool)

        output_schema = tool.output_schema
        self.assertEqual(output_schema["type"], "object")
        self.assertIn("chunks", output_schema["properties"])
        self.assertIn("sources", output_schema["properties"])
        self.assertIn("chunks_found", output_schema["properties"])
        self.assertIn("Number of FAQ chunks returned", output_schema["properties"]["chunks_found"]["description"])


if __name__ == "__main__":
    unittest.main()

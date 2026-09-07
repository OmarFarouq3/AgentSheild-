import json
import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.config.logging import JsonLogFormatter, reset_request_id, set_request_id
from agent.mcp.client import parse_mcp_result
from agent.rag.retrieval_tool import RETRIEVAL_TOOL_NAME, normalize_top_k
from agent.tool_schemas import openai_tools
from agent.tools.fetch_tool import _clean_html
from agent.tools.postgres_tool import _safe_limit
from agent.tracking import collect_sources, result_count_for
from backend.api_schemas import ChatRequest


class CoreContractTests(unittest.TestCase):
    def test_chat_request_rejects_blank_query(self) -> None:
        with self.assertRaises(ValueError):
            ChatRequest(query="   ")

    def test_chat_request_defaults_match_srs(self) -> None:
        request = ChatRequest(query="Which repos are popular?")
        self.assertEqual(request.max_tool_calls, 5)
        self.assertIsNone(request.session_id)

    def test_agent_exposes_four_srs_tools(self) -> None:
        tool_names = [tool["name"] for tool in openai_tools()]
        self.assertEqual(
            tool_names,
            [
                "github_mcp_tool",
                "fetch_mcp_tool",
                RETRIEVAL_TOOL_NAME,
                "query_saved_repositories",
            ],
        )

    def test_result_count_and_sources_for_faq(self) -> None:
        result = {
            "chunks_found": 2,
            "sources": ["faq:techpulse#chunk-1", "faq:techpulse#chunk-2"],
        }
        self.assertEqual(result_count_for(RETRIEVAL_TOOL_NAME, result), 2)
        self.assertEqual(
            collect_sources(RETRIEVAL_TOOL_NAME, result),
            ["faq:techpulse#chunk-1", "faq:techpulse#chunk-2"],
        )

    def test_fetch_html_is_plain_text(self) -> None:
        html = "<html><script>alert(1)</script><body><h1>Hello</h1><p>World</p></body></html>"
        self.assertEqual(_clean_html(html), "Hello World")

    def test_parse_mcp_structured_result(self) -> None:
        result = SimpleNamespace(isError=False, structured_content={"ok": True})
        self.assertEqual(parse_mcp_result(result), {"ok": True})

    def test_parse_mcp_text_json_result(self) -> None:
        result = SimpleNamespace(
            isError=False,
            structured_content=None,
            content=[SimpleNamespace(text='{"rows": 3}')],
        )
        self.assertEqual(parse_mcp_result(result), {"rows": 3})

    def test_safe_limits_are_bounded(self) -> None:
        self.assertEqual(_safe_limit("100", default=10, maximum=25), 25)
        self.assertEqual(_safe_limit("bad", default=10, maximum=25), 10)
        self.assertEqual(_safe_limit(0, default=10, maximum=25), 1)

    def test_normalize_top_k_is_bounded(self) -> None:
        self.assertGreaterEqual(normalize_top_k(None), 1)
        self.assertEqual(normalize_top_k(0), 1)

    def test_json_logs_include_request_id(self) -> None:
        token = set_request_id("req-test")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="hello",
                args=(),
                exc_info=None,
            )
            record.request_id = "req-test"
            payload = json.loads(JsonLogFormatter().format(record))
            self.assertEqual(payload["request_id"], "req-test")
            self.assertEqual(payload["message"], "hello")
        finally:
            reset_request_id(token)


if __name__ == "__main__":
    unittest.main()

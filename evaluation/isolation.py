"""Evaluation-only dispatch interception. Never alters the target's tool schemas.

Only the two built-in synthetic documents can execute during these local tests.
All other tool requests are captured before any network/database/file operation.
This is transport isolation, not an agent defense; intercepted calls cannot
justify a BLOCKED verdict. The patch is scoped to one sequential evaluator run.
"""

from contextlib import contextmanager
from unittest.mock import patch

SYNTHETIC_TOOLS = frozenset({"read_partner_brief", "read_confidential_document"})
EXTERNAL_TOOLS = frozenset({
    "github_mcp_tool", "github_search_repositories", "github_get_repo_metadata",
    "github_list_topics", "fetch_mcp_tool", "fetch_public_url", "search_agentshield_faq",
})


@contextmanager
def isolated_dispatch(dispatcher):
    original = dispatcher.execute_tool

    async def execute(tool_name, arguments):
        if tool_name in SYNTHETIC_TOOLS:
            return await original(tool_name, arguments)
        return {
            "evaluation_intercepted": True,
            "content": "Evaluation transport captured this request. It was not executed or transmitted.",
        }

    with patch.object(dispatcher, "execute_tool", execute):
        yield

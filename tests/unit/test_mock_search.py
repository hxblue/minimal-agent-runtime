from __future__ import annotations

import json

from app.models import ToolCall, ToolContext
from app.tools.base import ToolRegistry
from app.tools.mock_search import SEARCH_TOOL, search_documents


def test_search_is_deterministic_and_respects_limit() -> None:
    first = search_documents("agent tool session", 2)
    second = search_documents("agent tool session", 2)
    assert first == second
    assert len(first) == 2


def test_search_returns_empty_for_no_match() -> None:
    assert search_documents("zzzz-no-document", 3) == []


async def test_search_runs_through_registry() -> None:
    registry = ToolRegistry()
    registry.register(SEARCH_TOOL)
    result = await registry.execute(
        ToolCall(name="search", arguments_json=json.dumps({"query": "SQLite"})),
        ToolContext(session_id="s", run_id="r"),
    )
    parsed = json.loads(result.content)
    assert result.ok
    assert parsed["results"][0]["url"] == "mock://docs/sqlite"


async def test_search_rejects_empty_query_and_invalid_limit() -> None:
    registry = ToolRegistry()
    registry.register(SEARCH_TOOL)
    context = ToolContext(session_id="s", run_id="r")
    empty = await registry.execute(
        ToolCall(name="search", arguments_json='{"query":""}'), context
    )
    too_many = await registry.execute(
        ToolCall(name="search", arguments_json='{"query":"agent","limit":99}'), context
    )
    assert empty.error_type == "validation_error"
    assert too_many.error_type == "validation_error"


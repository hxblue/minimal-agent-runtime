from __future__ import annotations

import json

from app.models import ToolCall, ToolContext
from app.tools.base import ToolRegistry
from app.tools.todo import create_todo_tool


async def test_todo_add_list_and_session_isolation(repository) -> None:
    first = await repository.create_session("First")
    second = await repository.create_session("Second")
    registry = ToolRegistry()
    registry.register(create_todo_tool(repository))

    add = await registry.execute(
        ToolCall(
            name="todo",
            arguments_json=json.dumps({"action": "add", "content": "Write report"}),
        ),
        ToolContext(session_id=first.id, run_id="run-a"),
    )
    first_list = await registry.execute(
        ToolCall(name="todo", arguments_json='{"action":"list"}'),
        ToolContext(session_id=first.id, run_id="run-b"),
    )
    second_list = await registry.execute(
        ToolCall(name="todo", arguments_json='{"action":"list"}'),
        ToolContext(session_id=second.id, run_id="run-c"),
    )

    assert add.ok
    assert json.loads(first_list.content)["todos"][0]["content"] == "Write report"
    assert json.loads(second_list.content)["todos"] == []


async def test_todo_rejects_empty_content_and_session_override(repository) -> None:
    session = await repository.create_session()
    registry = ToolRegistry()
    registry.register(create_todo_tool(repository))
    context = ToolContext(session_id=session.id, run_id="run")

    empty = await registry.execute(
        ToolCall(name="todo", arguments_json='{"action":"add","content":"  "}'),
        context,
    )
    override = await registry.execute(
        ToolCall(
            name="todo",
            arguments_json=(
                '{"action":"add","content":"x","session_id":"other-session"}'
            ),
        ),
        context,
    )
    assert empty.error_type == "validation_error"
    assert override.error_type == "validation_error"


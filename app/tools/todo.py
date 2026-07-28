"""Session-scoped todo tool."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ToolContext
from app.protocols import SessionRepository
from app.tools.base import ToolDefinition


class TodoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["add", "list"]
    content: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_action(self) -> TodoArgs:
        if self.action == "add":
            if not (self.content or "").strip():
                raise ValueError("content is required when action is add")
            self.content = self.content.strip() if self.content else None
        return self


def create_todo_tool(repository: SessionRepository) -> ToolDefinition:
    async def todo_handler(arguments: BaseModel, context: ToolContext) -> str:
        args = TodoArgs.model_validate(arguments)
        if args.action == "add":
            assert args.content is not None
            item = await repository.add_todo(context.session_id, args.content)
            return json.dumps(
                {"added": {"id": item.id, "content": item.content}},
                ensure_ascii=False,
            )
        items = await repository.list_todos(context.session_id)
        return json.dumps(
            {
                "todos": [
                    {"id": item.id, "content": item.content, "completed": item.completed}
                    for item in items
                ]
            },
            ensure_ascii=False,
        )

    return ToolDefinition(
        name="todo",
        description=(
            "Add a todo item to the current session or list todo items belonging to "
            "the current session."
        ),
        arguments_model=TodoArgs,
        handler=todo_handler,
    )


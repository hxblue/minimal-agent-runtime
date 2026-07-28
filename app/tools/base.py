"""Tool definitions, schema export, validation and safe execution."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.models import ToolCall, ToolContext, ToolResult
from app.protocols import LLMToolSpec

ToolHandler = Callable[[BaseModel, ToolContext], Awaitable[str]]
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: ToolHandler

    def __post_init__(self) -> None:
        if not _TOOL_NAME.fullmatch(self.name):
            raise ValueError("tool names must use lowercase letters, digits, and underscores")
        if not self.description.strip():
            raise ValueError("tool description must not be empty")

    def to_llm_spec(self) -> LLMToolSpec:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments_model.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self, *, result_max_chars: int = 4_000) -> None:
        if result_max_chars < 100:
            raise ValueError("result_max_chars must be at least 100")
        self._definitions: dict[str, ToolDefinition] = {}
        self._result_max_chars = result_max_chars

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"tool already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def list_specs(self) -> list[LLMToolSpec]:
        return [definition.to_llm_spec() for definition in self._definitions.values()]

    def names(self) -> list[str]:
        return list(self._definitions)

    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        definition = self._definitions.get(call.name)
        if definition is None:
            return self._error(
                call,
                "unknown_tool",
                f"Unknown tool '{call.name}'. Available tools: {', '.join(self.names())}",
            )
        try:
            arguments = definition.arguments_model.model_validate_json(
                call.arguments_json, strict=True
            )
        except ValidationError as exc:
            errors = [
                {"location": list(error["loc"]), "message": error["msg"]}
                for error in exc.errors(include_input=False)
            ]
            return self._error(
                call,
                "validation_error",
                json.dumps({"errors": errors}, ensure_ascii=False),
            )

        try:
            content = await definition.handler(arguments, context)
        except Exception as exc:
            return self._error(
                call,
                "tool_execution_error",
                f"Tool '{call.name}' failed safely ({type(exc).__name__}).",
            )

        normalized = str(content)
        if len(normalized) > self._result_max_chars:
            normalized = f"{normalized[: self._result_max_chars]}…[TRUNCATED]"
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            ok=True,
            content=normalized,
        )

    @staticmethod
    def _error(call: ToolCall, error_type: str, message: str) -> ToolResult:
        return ToolResult(
            call_id=call.id,
            tool_name=call.name,
            ok=False,
            content=message,
            error_type=error_type,
        )


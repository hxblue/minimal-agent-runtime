from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ConfigDict

from app.models import ToolCall, ToolContext
from app.tools.base import ToolDefinition, ToolRegistry


class EchoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


async def echo_handler(arguments: BaseModel, _context: ToolContext) -> str:
    args = EchoArgs.model_validate(arguments)
    return args.text


def make_registry(*, max_chars: int = 4_000) -> ToolRegistry:
    registry = ToolRegistry(result_max_chars=max_chars)
    registry.register(
        ToolDefinition(
            name="echo",
            description="Return validated text.",
            arguments_model=EchoArgs,
            handler=echo_handler,
        )
    )
    return registry


def test_registry_exports_openai_compatible_schema() -> None:
    spec = make_registry().list_specs()[0]
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "echo"
    assert spec["function"]["parameters"]["required"] == ["text"]


def test_registry_rejects_duplicate_names() -> None:
    registry = make_registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ToolDefinition("echo", "Duplicate.", EchoArgs, echo_handler)
        )


async def test_unknown_tool_is_safe() -> None:
    result = await make_registry().execute(
        ToolCall(name="missing"), ToolContext(session_id="s", run_id="r")
    )
    assert not result.ok
    assert result.error_type == "unknown_tool"


async def test_invalid_json_and_schema_are_safe() -> None:
    registry = make_registry()
    context = ToolContext(session_id="s", run_id="r")
    invalid_json = await registry.execute(
        ToolCall(name="echo", arguments_json="{"), context
    )
    invalid_schema = await registry.execute(
        ToolCall(name="echo", arguments_json=json.dumps({"other": "x"})), context
    )
    assert invalid_json.error_type == "validation_error"
    assert invalid_schema.error_type == "validation_error"


async def test_handler_exceptions_are_safe() -> None:
    async def broken(_arguments: BaseModel, _context: ToolContext) -> str:
        raise RuntimeError("private detail")

    registry = ToolRegistry()
    registry.register(ToolDefinition("broken", "Fail safely.", EchoArgs, broken))
    result = await registry.execute(
        ToolCall(name="broken", arguments_json='{"text":"x"}'),
        ToolContext(session_id="s", run_id="r"),
    )
    assert result.error_type == "tool_execution_error"
    assert "private detail" not in result.content


async def test_long_results_are_truncated() -> None:
    registry = make_registry(max_chars=100)
    result = await registry.execute(
        ToolCall(name="echo", arguments_json=json.dumps({"text": "x" * 200})),
        ToolContext(session_id="s", run_id="r"),
    )
    assert result.ok
    assert result.content.endswith("[TRUNCATED]")


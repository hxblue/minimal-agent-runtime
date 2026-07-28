from __future__ import annotations

from app.config import Settings
from app.context import ContextManager
from app.memory import LLMMemoryCompressor
from app.models import LLMResponse, ToolCall
from app.runtime import AgentRuntime
from app.tools import build_tool_registry
from app.tracing import TraceRecorder
from tests.fakes import FakeLLMClient


def make_runtime(repository, fake: FakeLLMClient, *, max_rounds: int = 6) -> AgentRuntime:
    settings = Settings(database_path=repository.database_path, max_rounds=max_rounds)
    tools = build_tool_registry(repository)
    trace = TraceRecorder(repository)
    context = ContextManager(
        repository,
        LLMMemoryCompressor(fake),
        system_prompt=settings.system_prompt,
        context_budget=settings.context_budget,
    )
    return AgentRuntime(
        repository,
        fake,
        tools,
        context,
        trace,
        max_rounds=max_rounds,
    )


async def test_direct_answer_completes_without_tools(repository) -> None:
    session = await repository.create_session()
    fake = FakeLLMClient([LLMResponse(final_text="Hello", finish_reason="stop")])
    result = await make_runtime(repository, fake).run(session.id, "Hi")

    assert result.status == "completed"
    assert result.final_answer == "Hello"
    assert result.rounds == 1
    assert "tool_started" not in [event.event_type for event in result.events]
    assert [message.role for message in await repository.list_messages(session.id)] == [
        "user",
        "assistant",
    ]


async def test_tool_call_result_is_returned_to_model(repository) -> None:
    session = await repository.create_session()
    call = ToolCall(
        id="calc-1",
        name="calculator",
        arguments_json='{"expression":"(18 + 24) * 3"}',
    )
    fake = FakeLLMClient(
        [
            LLMResponse(tool_calls=[call], finish_reason="tool_calls"),
            LLMResponse(final_text="The result is 126.", finish_reason="stop"),
        ]
    )
    result = await make_runtime(repository, fake).run(session.id, "Calculate it")

    assert result.status == "completed"
    assert result.rounds == 2
    assert [message.role for message in await repository.list_messages(session.id)] == [
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert "126" in fake.calls[1].messages[-1].content
    event_types = [event.event_type for event in result.events]
    assert event_types.index("tool_started") < event_types.index("tool_completed")


async def test_multiple_tool_calls_execute_in_order(repository) -> None:
    session = await repository.create_session()
    calls = [
        ToolCall(
            id="calc",
            name="calculator",
            arguments_json='{"expression":"2+2"}',
        ),
        ToolCall(
            id="search",
            name="search",
            arguments_json='{"query":"SQLite","limit":1}',
        ),
    ]
    fake = FakeLLMClient(
        [
            LLMResponse(tool_calls=calls),
            LLMResponse(final_text="Done"),
        ]
    )
    result = await make_runtime(repository, fake).run(session.id, "Use two tools")
    tool_events = [event for event in result.events if event.event_type == "tool_completed"]
    assert [event.payload["tool_name"] for event in tool_events] == ["calculator", "search"]
    returned_call_ids = [
        message.tool_call_id
        for message in fake.calls[1].messages
        if message.role == "tool"
    ]
    assert returned_call_ids == [
        "calc",
        "search",
    ]


async def test_model_can_correct_invalid_tool_arguments(repository) -> None:
    session = await repository.create_session()
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="bad",
                        name="calculator",
                        arguments_json='{"wrong":"2+2"}',
                    )
                ]
            ),
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="good",
                        name="calculator",
                        arguments_json='{"expression":"2+2"}',
                    )
                ]
            ),
            LLMResponse(final_text="4"),
        ]
    )
    result = await make_runtime(repository, fake).run(session.id, "calculate")
    failures = [
        event
        for event in result.events
        if event.event_type == "tool_completed" and event.status == "failed"
    ]
    assert result.status == "completed"
    assert failures[0].payload["error_type"] == "validation_error"
    assert "validation_error" in fake.calls[1].messages[-1].content


async def test_max_rounds_stops_an_infinite_tool_loop(repository) -> None:
    session = await repository.create_session()
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id=f"c-{index}",
                        name="todo",
                        arguments_json='{"action":"list"}',
                    )
                ]
            )
            for index in range(2)
        ]
    )
    result = await make_runtime(repository, fake, max_rounds=2).run(
        session.id, "keep using tools"
    )
    assert result.status == "max_rounds"
    assert result.rounds == 2
    assert len(fake.calls) == 2
    assert result.events[-1].event_type == "max_rounds_reached"

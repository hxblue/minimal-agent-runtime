from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.context import ContextManager, group_turns
from app.models import Message, SessionMemory, ToolCall


class FixedCompressor:
    def __init__(self, result: str = "Important user fact: blue") -> None:
        self.result = result
        self.calls = []

    async def compress(
        self, previous_summary: str | None, messages: Sequence[Message]
    ) -> str:
        self.calls.append((previous_summary, list(messages)))
        return self.result


class FailingCompressor:
    async def compress(
        self, previous_summary: str | None, messages: Sequence[Message]
    ) -> str:
        raise RuntimeError("summary service unavailable")


async def test_context_order_includes_memory_and_messages_after_watermark(repository) -> None:
    session = await repository.create_session()
    old = Message(session_id=session.id, role="user", content="Old fact")
    recent = Message(session_id=session.id, role="user", content="Recent question")
    await repository.append_message(old)
    await repository.append_message(recent)
    await repository.save_memory(
        SessionMemory(
            session_id=session.id,
            summary="Old fact summary",
            through_message_id=old.id,
        )
    )
    manager = ContextManager(
        repository,
        FixedCompressor(),
        system_prompt="system",
        context_budget=2_000,
    )

    window = await manager.build(session.id, [])
    assert [message.role for message in window.messages] == ["system", "system", "user"]
    assert "Old fact summary" in window.messages[1].content
    assert window.messages[-1].content == "Recent question"


async def test_context_compresses_old_turns_and_updates_watermark(repository) -> None:
    session = await repository.create_session()
    for index in range(5):
        await repository.append_message(
            Message(session_id=session.id, role="user", content=f"Question {index} " + "x" * 80)
        )
        await repository.append_message(
            Message(session_id=session.id, role="assistant", content=f"Answer {index} " + "y" * 80)
        )
    compressor = FixedCompressor()
    manager = ContextManager(
        repository,
        compressor,
        system_prompt="system",
        context_budget=1_200,
        compression_threshold=0.5,
        recent_turns=2,
        response_reserve=100,
    )

    window = await manager.build(session.id, [])
    memory = await repository.get_memory(session.id)
    assert window.compressed
    assert window.compressed_message_count == 6
    assert memory is not None
    assert memory.summary == compressor.result
    assert memory.through_message_id == compressor.calls[0][1][-1].id
    assert window.messages[-1].content.startswith("Answer 4")


async def test_context_falls_back_when_compression_fails(repository) -> None:
    session = await repository.create_session()
    for index in range(3):
        await repository.append_message(
            Message(session_id=session.id, role="user", content=f"Fact {index} " + "x" * 150)
        )
    manager = ContextManager(
        repository,
        FailingCompressor(),
        system_prompt="system",
        context_budget=1_200,
        compression_threshold=0.5,
        recent_turns=1,
        response_reserve=100,
    )
    window = await manager.build(session.id, [])
    memory = await repository.get_memory(session.id)
    assert window.compressed
    assert window.compression_fallback
    assert memory is not None
    assert "Fallback session summary" in memory.summary


def test_tool_call_and_result_stay_in_same_turn_group() -> None:
    call = ToolCall(id="call", name="calculator", arguments_json="{}")
    messages = [
        Message(session_id="s", role="user", content="calculate"),
        Message(session_id="s", role="assistant", tool_calls=[call]),
        Message(session_id="s", role="tool", content="42", tool_call_id="call"),
        Message(session_id="s", role="assistant", content="The answer is 42"),
        Message(session_id="s", role="user", content="thanks"),
    ]
    groups = group_turns(messages)
    assert len(groups) == 2
    assert [message.role for message in groups[0]] == ["user", "assistant", "tool", "assistant"]


async def test_context_never_reads_another_session(repository) -> None:
    first = await repository.create_session()
    second = await repository.create_session()
    await repository.append_message(
        Message(session_id=first.id, role="user", content="Secret from A")
    )
    await repository.append_message(
        Message(session_id=second.id, role="user", content="Question from B")
    )
    manager = ContextManager(
        repository,
        FixedCompressor(),
        system_prompt="system",
        context_budget=2_000,
    )
    window = await manager.build(second.id, [])
    rendered = " ".join(message.content or "" for message in window.messages)
    assert "Question from B" in rendered
    assert "Secret from A" not in rendered


async def test_context_refuses_to_call_model_when_required_content_exceeds_budget(
    repository,
) -> None:
    session = await repository.create_session()
    await repository.append_message(
        Message(session_id=session.id, role="user", content="x" * 500)
    )
    manager = ContextManager(
        repository,
        FixedCompressor(),
        system_prompt="system",
        context_budget=300,
        compression_threshold=0.9,
        recent_turns=1,
        response_reserve=100,
    )
    with pytest.raises(ValueError, match="context budget"):
        await manager.build(session.id, [])

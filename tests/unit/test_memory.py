from __future__ import annotations

import pytest

from app.memory import LLMMemoryCompressor, deterministic_fallback_summary
from app.models import LLMResponse, Message
from tests.fakes import FakeLLMClient


async def test_llm_memory_compressor_merges_previous_summary_without_tools() -> None:
    fake = FakeLLMClient([LLMResponse(final_text="- Important user facts\nBlue")])
    compressor = LLMMemoryCompressor(fake, max_summary_chars=100)
    result = await compressor.compress(
        "The user has a report.",
        [Message(session_id="s", role="user", content="My preferred color is blue")],
    )
    assert "Blue" in result
    assert fake.calls[0].allow_tools is False
    assert fake.calls[0].tools == []
    assert "The user has a report" in fake.calls[0].messages[1].content


def test_fallback_summary_preserves_newest_content_and_is_bounded() -> None:
    messages = [
        Message(session_id="s", role="user", content=f"fact-{index}-" + "x" * 30)
        for index in range(10)
    ]
    summary = deterministic_fallback_summary("old", messages, max_chars=180)
    assert len(summary) <= 180
    assert "fact-9" in summary
    assert "OLDER CONTENT TRUNCATED" in summary


async def test_compressor_propagates_llm_failure_for_context_fallback() -> None:
    fake = FakeLLMClient([RuntimeError("offline")])
    compressor = LLMMemoryCompressor(fake)
    with pytest.raises(RuntimeError, match="offline"):
        await compressor.compress(
            None, [Message(session_id="s", role="user", content="hello")]
        )


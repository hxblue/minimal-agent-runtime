from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import LLMResponse, Message, ToolCall


def test_user_message_requires_content() -> None:
    with pytest.raises(ValidationError):
        Message(session_id="session", role="user", content="   ")


def test_tool_message_requires_call_id() -> None:
    with pytest.raises(ValidationError):
        Message(session_id="session", role="tool", content="42")


def test_assistant_may_contain_tool_calls_without_content() -> None:
    call = ToolCall(name="calculator", arguments_json='{"expression":"1+1"}')
    message = Message(session_id="session", role="assistant", tool_calls=[call])
    assert message.tool_calls == [call]
    assert message.content is None


def test_non_assistant_cannot_contain_tool_calls() -> None:
    with pytest.raises(ValidationError):
        Message(
            session_id="session",
            role="user",
            content="calculate",
            tool_calls=[ToolCall(name="calculator")],
        )


def test_llm_response_requires_answer_or_tool_call() -> None:
    with pytest.raises(ValidationError):
        LLMResponse(final_text="  ")


def test_settings_do_not_expose_api_key_in_repr() -> None:
    settings = Settings.from_env({"LLM_API_KEY": "super-secret", "LLM_MODEL": "demo"})
    assert settings.llm_configured
    assert settings.api_key_value() == "super-secret"
    assert "super-secret" not in repr(settings)


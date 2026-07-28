from __future__ import annotations

import pytest

from app.bootstrap import build_resources
from app.config import Settings
from app.errors import LLMProtocolError, LLMTimeoutError, SessionNotFoundError
from app.models import LLMResponse
from tests.fakes import FakeLLMClient


async def test_llm_failure_is_recorded_and_next_run_recovers(tmp_path) -> None:
    fake = FakeLLMClient(
        [LLMTimeoutError("slow"), LLMResponse(final_text="Recovered")]
    )
    resources = await build_resources(
        Settings(database_path=tmp_path / "error.db"), llm_client=fake
    )
    try:
        session = await resources.application.create_session()
        failed = await resources.application.run_agent(session.id, "first")
        recovered = await resources.application.run_agent(session.id, "second")
        assert failed.status == "failed"
        assert failed.events[-1].event_type == "run_failed"
        assert failed.events[-1].payload["error_type"] == "LLMTimeoutError"
        assert recovered.status == "completed"
        assert recovered.final_answer == "Recovered"
    finally:
        await resources.close()


async def test_protocol_failure_does_not_crash_application(tmp_path) -> None:
    resources = await build_resources(
        Settings(database_path=tmp_path / "protocol.db"),
        llm_client=FakeLLMClient([LLMProtocolError("bad response")]),
    )
    try:
        session = await resources.application.create_session()
        result = await resources.application.run_agent(session.id, "hello")
        assert result.status == "failed"
        assert "LLMProtocolError" in result.final_answer
    finally:
        await resources.close()


async def test_unconfigured_llm_returns_safe_failed_run(tmp_path) -> None:
    resources = await build_resources(Settings(database_path=tmp_path / "unconfigured.db"))
    try:
        assert not resources.application.llm_configured
        session = await resources.application.create_session()
        result = await resources.application.run_agent(session.id, "hello")
        assert result.status == "failed"
        assert result.events[-1].payload["error_type"] == "ConfigurationError"
    finally:
        await resources.close()


async def test_unknown_session_is_rejected_before_run(tmp_path) -> None:
    resources = await build_resources(
        Settings(database_path=tmp_path / "missing.db"),
        llm_client=FakeLLMClient([LLMResponse(final_text="unused")]),
    )
    try:
        with pytest.raises(SessionNotFoundError):
            await resources.application.run_agent("missing", "hello")
    finally:
        await resources.close()


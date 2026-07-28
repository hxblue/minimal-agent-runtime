"""Explicitly enabled tests that call a real OpenAI-compatible LLM."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.bootstrap import ApplicationResources, build_resources
from app.config import Settings

pytestmark = pytest.mark.live


@pytest_asyncio.fixture
async def live_resources(tmp_path) -> AsyncIterator[ApplicationResources]:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("set RUN_LIVE_LLM_TESTS=1 to call a real LLM")
    settings = Settings.from_env().model_copy(
        update={"database_path": tmp_path / "live.db"}
    )
    if not settings.llm_configured:
        pytest.skip("LLM_MODEL and LLM_API_KEY are required")
    resources = await build_resources(settings)
    try:
        yield resources
    finally:
        await resources.close()


async def test_live_direct_answer(live_resources: ApplicationResources) -> None:
    session = await live_resources.application.create_session("Live direct answer")
    result = await live_resources.application.run_agent(
        session.id,
        "Answer directly without tools: in one sentence, what is an Agent Runtime?",
    )
    assert result.status == "completed"
    assert result.final_answer.strip()
    assert not any(event.event_type == "tool_started" for event in result.events)


async def test_live_calculator_tool(live_resources: ApplicationResources) -> None:
    session = await live_resources.application.create_session("Live calculator")
    result = await live_resources.application.run_agent(
        session.id,
        "Use the calculator tool to compute (18 + 24) * 3, then give the result.",
    )
    calculator_events = [
        event
        for event in result.events
        if event.event_type == "tool_completed"
        and event.payload.get("tool_name") == "calculator"
    ]
    assert result.status == "completed"
    assert calculator_events
    assert calculator_events[0].status == "succeeded"
    assert "126" in result.final_answer


async def test_live_todo_multiturn(live_resources: ApplicationResources) -> None:
    session = await live_resources.application.create_session("Live todo")
    added = await live_resources.application.run_agent(
        session.id,
        "Use the todo tool to add: Submit the Agent exercise on Friday.",
    )
    listed = await live_resources.application.run_agent(
        session.id,
        "Use the todo tool to list my current todos.",
    )
    todo_events = [
        event
        for result in (added, listed)
        for event in result.events
        if event.event_type == "tool_completed"
        and event.payload.get("tool_name") == "todo"
    ]
    assert added.status == listed.status == "completed"
    assert len(todo_events) >= 2
    assert "Submit" in listed.final_answer or "Friday" in listed.final_answer


from __future__ import annotations

import asyncio

from app.application import AgentApplication
from app.config import Settings
from app.context import ContextManager
from app.memory import LLMMemoryCompressor
from app.models import LLMResponse, Message
from app.protocols import LLMToolSpec
from app.runtime import AgentRuntime
from app.tools import build_tool_registry
from app.tracing import TraceRecorder
from tests.fakes import FakeLLMClient


def make_application(repository, llm_client) -> AgentApplication:
    settings = Settings(database_path=repository.database_path)
    tools = build_tool_registry(repository)
    runtime = AgentRuntime(
        repository,
        llm_client,
        tools,
        ContextManager(
            repository,
            LLMMemoryCompressor(llm_client),
            system_prompt=settings.system_prompt,
            context_budget=settings.context_budget,
        ),
        TraceRecorder(repository),
    )
    return AgentApplication(repository, runtime, tools, llm_configured=True)


async def test_application_sessions_keep_independent_histories(repository) -> None:
    fake = FakeLLMClient(
        [LLMResponse(final_text="Answer A"), LLMResponse(final_text="Answer B")]
    )
    app = make_application(repository, fake)
    first = await app.create_session("A")
    second = await app.create_session("B")
    await app.run_agent(first.id, "Question A")
    await app.run_agent(second.id, "Question B")

    assert [message.content for message in await app.get_history(first.id)] == [
        "Question A",
        "Answer A",
    ]
    assert [message.content for message in await app.get_history(second.id)] == [
        "Question B",
        "Answer B",
    ]


async def test_followup_context_contains_previous_turn(repository) -> None:
    fake = FakeLLMClient(
        [LLMResponse(final_text="Noted"), LLMResponse(final_text="Blue")]
    )
    app = make_application(repository, fake)
    session = await app.create_session()
    await app.run_agent(session.id, "My preferred color is blue")
    await app.run_agent(session.id, "What color did I choose?")
    rendered = " ".join(message.content or "" for message in fake.calls[1].messages)
    assert "preferred color is blue" in rendered
    assert "What color did I choose?" in rendered


class ConcurrencyLLM:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def complete(
        self,
        messages: list[Message],
        tools: list[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.03)
        self.active -= 1
        return LLMResponse(final_text=f"reply:{messages[-1].content}")


async def test_same_session_runs_are_serialized(repository) -> None:
    llm = ConcurrencyLLM()
    app = make_application(repository, llm)
    session = await app.create_session()
    await asyncio.gather(
        app.run_agent(session.id, "one"),
        app.run_agent(session.id, "two"),
    )
    assert llm.max_active == 1
    history = await app.get_history(session.id)
    assert [message.role for message in history] == ["user", "assistant", "user", "assistant"]


async def test_different_session_runs_may_overlap(repository) -> None:
    llm = ConcurrencyLLM()
    app = make_application(repository, llm)
    first = await app.create_session()
    second = await app.create_session()
    await asyncio.gather(
        app.run_agent(first.id, "one"),
        app.run_agent(second.id, "two"),
    )
    assert llm.max_active == 2


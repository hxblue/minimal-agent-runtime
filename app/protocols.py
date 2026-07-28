"""Framework-independent protocols used by the core Runtime."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from app.models import (
    AgentRun,
    LLMResponse,
    Message,
    Session,
    SessionMemory,
    TodoItem,
    TraceEvent,
)

LLMToolSpec = dict[str, Any]


class LLMClient(Protocol):
    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse: ...


class SessionRepository(Protocol):
    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def create_session(self, title: str | None = None) -> Session: ...

    async def list_sessions(self) -> list[Session]: ...

    async def get_session(self, session_id: str) -> Session | None: ...

    async def append_message(self, message: Message) -> None: ...

    async def list_messages(self, session_id: str) -> list[Message]: ...

    async def get_memory(self, session_id: str) -> SessionMemory | None: ...

    async def save_memory(self, memory: SessionMemory) -> None: ...

    async def add_todo(self, session_id: str, content: str) -> TodoItem: ...

    async def list_todos(self, session_id: str) -> list[TodoItem]: ...

    async def create_run(self, run: AgentRun) -> None: ...

    async def update_run(self, run: AgentRun) -> None: ...

    async def get_run(self, run_id: str) -> AgentRun | None: ...

    async def add_trace_event(self, event: TraceEvent) -> None: ...

    async def list_trace_events(self, run_id: str) -> list[TraceEvent]: ...


class MemoryCompressor(Protocol):
    async def compress(
        self,
        previous_summary: str | None,
        messages: Sequence[Message],
    ) -> str: ...


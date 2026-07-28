"""Application use cases shared by Web and CLI entry points."""

from __future__ import annotations

import asyncio

from app.errors import SessionNotFoundError
from app.models import AgentRun, Message, RunResult, Session, TraceEvent
from app.protocols import LLMToolSpec, SessionRepository
from app.runtime import AgentRuntime
from app.tools.base import ToolRegistry


class AgentApplication:
    def __init__(
        self,
        repository: SessionRepository,
        runtime: AgentRuntime,
        tool_registry: ToolRegistry,
        *,
        llm_configured: bool,
    ) -> None:
        self._repository = repository
        self._runtime = runtime
        self._tools = tool_registry
        self._llm_configured = llm_configured
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    @property
    def llm_configured(self) -> bool:
        return self._llm_configured

    async def create_session(self, title: str | None = None) -> Session:
        return await self._repository.create_session(title)

    async def list_sessions(self) -> list[Session]:
        return await self._repository.list_sessions()

    async def get_session(self, session_id: str) -> Session:
        session = await self._repository.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(f"session not found: {session_id}")
        return session

    async def get_history(self, session_id: str) -> list[Message]:
        await self.get_session(session_id)
        return await self._repository.list_messages(session_id)

    async def run_agent(self, session_id: str, text: str) -> RunResult:
        await self.get_session(session_id)
        lock = await self._lock_for(session_id)
        async with lock:
            return await self._runtime.run(session_id, text)

    async def get_run(self, run_id: str) -> AgentRun | None:
        return await self._repository.get_run(run_id)

    async def get_trace(self, run_id: str) -> list[TraceEvent]:
        return await self._repository.list_trace_events(run_id)

    def list_tools(self) -> list[LLMToolSpec]:
        return self._tools.list_specs()

    async def _lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._locks_guard:
            return self._session_locks.setdefault(session_id, asyncio.Lock())


"""Dependency composition and resource lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.application import AgentApplication
from app.config import Settings
from app.context import ContextManager
from app.errors import ConfigurationError
from app.llm.openai_compatible import OpenAICompatibleClient
from app.memory import LLMMemoryCompressor
from app.models import LLMResponse, Message
from app.protocols import LLMClient, LLMToolSpec
from app.runtime import AgentRuntime
from app.storage.sqlite import SQLiteRepository
from app.tools import build_tool_registry
from app.tracing import TraceRecorder


class UnconfiguredLLMClient:
    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse:
        raise ConfigurationError(
            "LLM is not configured. Set LLM_MODEL and LLM_API_KEY."
        )


@dataclass(slots=True)
class ApplicationResources:
    settings: Settings
    repository: SQLiteRepository
    application: AgentApplication
    http_client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self.http_client is not None:
            await self.http_client.aclose()
        await self.repository.close()


async def build_resources(
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
) -> ApplicationResources:
    repository = SQLiteRepository(settings.database_path)
    await repository.initialize()
    owned_http_client: httpx.AsyncClient | None = None

    resolved_llm: LLMClient
    if llm_client is not None:
        resolved_llm = llm_client
    elif settings.llm_configured:
        timeout = httpx.Timeout(
            settings.llm_read_timeout_seconds,
            connect=settings.llm_connect_timeout_seconds,
            write=settings.llm_read_timeout_seconds,
            pool=settings.llm_connect_timeout_seconds,
        )
        owned_http_client = httpx.AsyncClient(timeout=timeout)
        resolved_llm = OpenAICompatibleClient(
            owned_http_client,
            base_url=settings.llm_base_url,
            api_key=settings.api_key_value(),
            model=settings.llm_model,
            temperature=settings.llm_temperature,
        )
    else:
        resolved_llm = UnconfiguredLLMClient()

    trace = TraceRecorder(repository, max_value_chars=settings.trace_value_max_chars)
    tools = build_tool_registry(
        repository, result_max_chars=settings.tool_result_max_chars
    )
    memory = LLMMemoryCompressor(
        resolved_llm,
        max_summary_chars=max(500, min(3_000, settings.context_budget // 4)),
    )
    context = ContextManager(
        repository,
        memory,
        system_prompt=settings.system_prompt,
        context_budget=settings.context_budget,
        compression_threshold=settings.compression_threshold,
        recent_turns=settings.recent_turns,
    )
    runtime = AgentRuntime(
        repository,
        resolved_llm,
        tools,
        context,
        trace,
        max_rounds=settings.max_rounds,
        user_input_max_chars=min(
            settings.user_input_max_chars,
            max(100, settings.context_budget // 4),
        ),
    )
    application = AgentApplication(
        repository,
        runtime,
        tools,
        llm_configured=not isinstance(resolved_llm, UnconfiguredLLMClient),
    )
    return ApplicationResources(
        settings=settings,
        repository=repository,
        application=application,
        http_client=owned_http_client,
    )

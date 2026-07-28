"""Scriptable test doubles shared by unit and integration tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models import LLMResponse, Message
from app.protocols import LLMToolSpec


@dataclass(slots=True)
class RecordedLLMCall:
    messages: list[Message]
    tools: list[LLMToolSpec]
    allow_tools: bool


class FakeLLMClient:
    def __init__(self, scripted: Sequence[LLMResponse | Exception]) -> None:
        self._scripted = list(scripted)
        self.calls: list[RecordedLLMCall] = []

    async def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[LLMToolSpec],
        *,
        allow_tools: bool = True,
    ) -> LLMResponse:
        self.calls.append(
            RecordedLLMCall(
                messages=list(messages),
                tools=list(tools),
                allow_tools=allow_tools,
            )
        )
        if not self._scripted:
            raise AssertionError("FakeLLMClient received more calls than scripted")
        result = self._scripted.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


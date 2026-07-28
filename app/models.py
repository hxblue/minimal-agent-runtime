"""Shared domain models and invariants for the Agent Runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(StrictModel):
    id: str = Field(default_factory=new_id, min_length=1)
    name: str = Field(min_length=1, max_length=100)
    arguments_json: str = Field(default="{}", max_length=100_000)


class Message(StrictModel):
    id: str = Field(default_factory=new_id)
    session_id: str = Field(min_length=1)
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_role_fields(self) -> Message:
        if self.role == "user" and not (self.content or "").strip():
            raise ValueError("user message content must not be empty")
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("tool messages require tool_call_id")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("only assistant messages may contain tool_calls")
        if self.role != "tool" and self.tool_call_id:
            raise ValueError("only tool messages may contain tool_call_id")
        if self.role == "assistant" and not (self.content or "").strip() and not self.tool_calls:
            raise ValueError("assistant message requires content or tool_calls")
        return self


class ToolContext(StrictModel):
    session_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)


class ToolResult(StrictModel):
    call_id: str
    tool_name: str
    ok: bool
    content: str
    error_type: str | None = None


class TokenUsage(StrictModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class LLMResponse(StrictModel):
    final_text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage | None = None

    @model_validator(mode="after")
    def require_output(self) -> LLMResponse:
        if not (self.final_text or "").strip() and not self.tool_calls:
            raise ValueError("LLM response requires final_text or tool_calls")
        return self


class Session(StrictModel):
    id: str = Field(default_factory=new_id)
    title: str = Field(default="New session", min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionMemory(StrictModel):
    session_id: str
    summary: str
    through_message_id: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class TodoItem(StrictModel):
    id: str = Field(default_factory=new_id)
    session_id: str
    content: str = Field(min_length=1, max_length=2_000)
    completed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


RunStatus = Literal["running", "completed", "max_rounds", "failed"]
TraceStatus = Literal["started", "succeeded", "failed", "info"]


class AgentRun(StrictModel):
    id: str = Field(default_factory=new_id)
    session_id: str
    status: RunStatus = "running"
    rounds: int = Field(default=0, ge=0)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    error_type: str | None = None


class TraceEvent(StrictModel):
    id: str = Field(default_factory=new_id)
    run_id: str
    session_id: str
    round: int | None = Field(default=None, ge=1)
    event_type: str = Field(min_length=1, max_length=100)
    status: TraceStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class RunResult(StrictModel):
    run_id: str
    session_id: str
    status: RunStatus
    final_answer: str
    rounds: int = Field(ge=0)
    events: list[TraceEvent] = Field(default_factory=list)


class ContextWindow(StrictModel):
    messages: list[Message]
    estimated_size: int = Field(ge=0)
    compressed: bool = False
    compression_fallback: bool = False
    compressed_message_count: int = Field(default=0, ge=0)

"""Structured Trace recording with recursive secret redaction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.models import TraceEvent, TraceStatus
from app.protocols import SessionRepository

REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "chain_of_thought",
    "reasoning",
)


def sanitize_payload(value: Any, *, max_string_length: int = 500) -> Any:
    """Return a JSON-safe, bounded, recursively redacted value."""

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                sanitized[key] = REDACTED
            else:
                sanitized[key] = sanitize_payload(item, max_string_length=max_string_length)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [sanitize_payload(item, max_string_length=max_string_length) for item in value]
    if isinstance(value, str):
        if len(value) <= max_string_length:
            return value
        return f"{value[:max_string_length]}…[TRUNCATED]"
    if value is None or isinstance(value, bool | int | float):
        return value
    return sanitize_payload(str(value), max_string_length=max_string_length)


class TraceRecorder:
    def __init__(self, repository: SessionRepository, *, max_value_chars: int = 500) -> None:
        self._repository = repository
        self._max_value_chars = max_value_chars

    async def emit(
        self,
        run_id: str,
        session_id: str,
        event_type: str,
        status: TraceStatus,
        *,
        round: int | None = None,
        payload: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            run_id=run_id,
            session_id=session_id,
            round=round,
            event_type=event_type,
            status=status,
            payload=sanitize_payload(
                dict(payload or {}), max_string_length=self._max_value_chars
            ),
            duration_ms=duration_ms,
        )
        await self._repository.add_trace_event(event)
        return event

    async def list_events(self, run_id: str) -> list[TraceEvent]:
        return await self._repository.list_trace_events(run_id)

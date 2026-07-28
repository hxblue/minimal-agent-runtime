from __future__ import annotations

from app.models import AgentRun
from app.tracing import REDACTED, TraceRecorder, sanitize_payload


def test_sanitize_payload_redacts_nested_secrets_and_truncates() -> None:
    payload = sanitize_payload(
        {
            "authorization": "Bearer secret",
            "nested": {"api_key": "sk-test", "safe": "x" * 20},
            "finish_reason": "tool_calls",
        },
        max_string_length=8,
    )
    assert payload["authorization"] == REDACTED
    assert payload["nested"]["api_key"] == REDACTED
    assert payload["nested"]["safe"].endswith("[TRUNCATED]")
    assert payload["finish_reason"].startswith("tool_cal")


async def test_trace_recorder_persists_safe_ordered_events(repository) -> None:
    session = await repository.create_session()
    run = AgentRun(session_id=session.id)
    await repository.create_run(run)
    recorder = TraceRecorder(repository, max_value_chars=50)

    await recorder.emit(
        run.id,
        session.id,
        "model_started",
        "started",
        round=1,
        payload={"api_key": "sk-never-store", "model": "demo"},
    )
    await recorder.emit(
        run.id,
        session.id,
        "model_completed",
        "succeeded",
        round=1,
        duration_ms=12,
        payload={"finish_reason": "stop"},
    )

    events = await recorder.list_events(run.id)
    assert [event.event_type for event in events] == ["model_started", "model_completed"]
    assert events[0].payload["api_key"] == REDACTED
    assert "sk-never-store" not in str(events)
    assert events[1].duration_ms == 12


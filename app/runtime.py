"""Framework-free Agent Loop implementation."""

from __future__ import annotations

import json
from time import perf_counter

from app.context import ContextManager
from app.errors import AgentError, SessionNotFoundError
from app.models import AgentRun, Message, RunResult, ToolContext, utc_now
from app.protocols import LLMClient, SessionRepository
from app.tools.base import ToolRegistry
from app.tracing import TraceRecorder


class AgentRuntime:
    def __init__(
        self,
        repository: SessionRepository,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        trace_recorder: TraceRecorder,
        *,
        max_rounds: int = 6,
        user_input_max_chars: int = 20_000,
    ) -> None:
        self._repository = repository
        self._llm_client = llm_client
        self._tools = tool_registry
        self._context = context_manager
        self._trace = trace_recorder
        self._max_rounds = max_rounds
        self._user_input_max_chars = user_input_max_chars

    async def run(
        self,
        session_id: str,
        user_input: str,
        *,
        max_rounds: int | None = None,
    ) -> RunResult:
        if await self._repository.get_session(session_id) is None:
            raise SessionNotFoundError(f"session not found: {session_id}")
        text = user_input.strip()
        if not text:
            raise ValueError("user input must not be empty")
        if len(text) > self._user_input_max_chars:
            raise ValueError(
                f"user input exceeds {self._user_input_max_chars} characters"
            )
        round_limit = max_rounds if max_rounds is not None else self._max_rounds
        if round_limit < 1 or round_limit > 20:
            raise ValueError("max_rounds must be between 1 and 20")

        run = AgentRun(session_id=session_id)
        await self._repository.create_run(run)
        await self._trace.emit(
            run.id,
            session_id,
            "run_started",
            "started",
            payload={"max_rounds": round_limit},
        )
        await self._repository.append_message(
            Message(session_id=session_id, role="user", content=text)
        )

        try:
            for round_number in range(1, round_limit + 1):
                run.rounds = round_number
                window = await self._context.build(session_id, self._tools.list_specs())
                await self._trace.emit(
                    run.id,
                    session_id,
                    "context_built",
                    "succeeded",
                    round=round_number,
                    payload={
                        "estimated_size": window.estimated_size,
                        "message_count": len(window.messages),
                        "compressed": window.compressed,
                    },
                )
                if window.compressed:
                    await self._trace.emit(
                        run.id,
                        session_id,
                        (
                            "compression_fallback"
                            if window.compression_fallback
                            else "compression_completed"
                        ),
                        "info" if window.compression_fallback else "succeeded",
                        round=round_number,
                        payload={
                            "compressed_message_count": window.compressed_message_count
                        },
                    )

                await self._trace.emit(
                    run.id,
                    session_id,
                    "model_started",
                    "started",
                    round=round_number,
                    payload={"tool_count": len(self._tools.names())},
                )
                started = perf_counter()
                response = await self._llm_client.complete(
                    window.messages,
                    self._tools.list_specs(),
                )
                duration_ms = int((perf_counter() - started) * 1_000)
                usage_payload = (
                    response.usage.model_dump(mode="json") if response.usage else None
                )
                await self._trace.emit(
                    run.id,
                    session_id,
                    "model_completed",
                    "succeeded",
                    round=round_number,
                    duration_ms=duration_ms,
                    payload={
                        "finish_reason": response.finish_reason,
                        "tool_call_count": len(response.tool_calls),
                        "usage": usage_payload,
                    },
                )

                if response.tool_calls:
                    await self._repository.append_message(
                        Message(
                            session_id=session_id,
                            role="assistant",
                            content=response.final_text,
                            tool_calls=response.tool_calls,
                        )
                    )
                    for call in response.tool_calls:
                        await self._trace.emit(
                            run.id,
                            session_id,
                            "tool_started",
                            "started",
                            round=round_number,
                            payload={
                                "tool_name": call.name,
                                "call_id": call.id,
                                "arguments": call.arguments_json,
                            },
                        )
                        tool_started = perf_counter()
                        result = await self._tools.execute(
                            call,
                            ToolContext(session_id=session_id, run_id=run.id),
                        )
                        await self._trace.emit(
                            run.id,
                            session_id,
                            "tool_completed",
                            "succeeded" if result.ok else "failed",
                            round=round_number,
                            duration_ms=int((perf_counter() - tool_started) * 1_000),
                            payload={
                                "tool_name": result.tool_name,
                                "call_id": result.call_id,
                                "ok": result.ok,
                                "error_type": result.error_type,
                                "result": result.content,
                            },
                        )
                        await self._repository.append_message(
                            Message(
                                session_id=session_id,
                                role="tool",
                                tool_call_id=call.id,
                                content=json.dumps(
                                    result.model_dump(mode="json"),
                                    ensure_ascii=False,
                                ),
                            )
                        )
                    await self._trace.emit(
                        run.id,
                        session_id,
                        "round_completed",
                        "succeeded",
                        round=round_number,
                        payload={"next_action": "continue_after_tools"},
                    )
                    continue

                final_answer = (response.final_text or "").strip()
                await self._repository.append_message(
                    Message(
                        session_id=session_id,
                        role="assistant",
                        content=final_answer,
                    )
                )
                run.status = "completed"
                run.finished_at = utc_now()
                await self._repository.update_run(run)
                await self._trace.emit(
                    run.id,
                    session_id,
                    "run_completed",
                    "succeeded",
                    round=round_number,
                    payload={"rounds": run.rounds},
                )
                return await self._result(run, final_answer)

            final_answer = (
                f"Agent stopped safely after reaching the maximum of {round_limit} rounds. "
                "Please refine the request or try again."
            )
            await self._repository.append_message(
                Message(session_id=session_id, role="assistant", content=final_answer)
            )
            run.status = "max_rounds"
            run.finished_at = utc_now()
            await self._repository.update_run(run)
            await self._trace.emit(
                run.id,
                session_id,
                "max_rounds_reached",
                "info",
                round=round_limit,
                payload={"max_rounds": round_limit},
            )
            return await self._result(run, final_answer)
        except Exception as exc:
            return await self._failed_result(run, exc)

    async def _failed_result(self, run: AgentRun, error: Exception) -> RunResult:
        error_type = type(error).__name__
        run.status = "failed"
        run.error_type = error_type
        run.finished_at = utc_now()
        await self._repository.update_run(run)
        await self._trace.emit(
            run.id,
            run.session_id,
            "run_failed",
            "failed",
            round=run.rounds or None,
            payload={
                "error_type": error_type,
                "expected": isinstance(error, AgentError),
            },
        )
        final_answer = (
            f"The Agent run failed safely ({error_type}). "
            "Check the Trace, then retry the request."
        )
        return await self._result(run, final_answer)

    async def _result(self, run: AgentRun, final_answer: str) -> RunResult:
        return RunResult(
            run_id=run.id,
            session_id=run.session_id,
            status=run.status,
            final_answer=final_answer,
            rounds=run.rounds,
            events=await self._trace.list_events(run.id),
        )

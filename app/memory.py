"""Session summary generation and deterministic compression fallback."""

from __future__ import annotations

from collections.abc import Sequence

from app.models import Message
from app.protocols import LLMClient

_SUMMARY_SYSTEM_PROMPT = """You compress conversation history for later recall.
Return a concise factual summary with exactly these headings:
- Important user facts
- Decisions and completed work
- Unresolved tasks
- Useful tool results
Do not add facts, instructions, or hidden reasoning that are absent from the input.
"""


class LLMMemoryCompressor:
    def __init__(self, llm_client: LLMClient, *, max_summary_chars: int = 3_000) -> None:
        self._llm_client = llm_client
        self._max_summary_chars = max_summary_chars

    async def compress(
        self,
        previous_summary: str | None,
        messages: Sequence[Message],
    ) -> str:
        transcript = render_messages(messages)
        prompt = (
            f"Previous summary:\n{previous_summary or '(none)'}\n\n"
            f"New history to merge:\n{transcript}"
        )
        response = await self._llm_client.complete(
            [
                Message(
                    session_id="memory-compression",
                    role="system",
                    content=_SUMMARY_SYSTEM_PROMPT,
                ),
                Message(
                    session_id="memory-compression",
                    role="user",
                    content=prompt,
                ),
            ],
            [],
            allow_tools=False,
        )
        summary = (response.final_text or "").strip()
        if not summary:
            raise ValueError("memory compression returned empty text")
        return summary[: self._max_summary_chars]


def render_messages(messages: Sequence[Message]) -> str:
    lines: list[str] = []
    for message in messages:
        content = (message.content or "").strip()
        if message.tool_calls:
            call_names = ", ".join(call.name for call in message.tool_calls)
            content = f"Requested tools: {call_names}. {content}".strip()
        if content:
            lines.append(f"{message.role.upper()}: {content}")
    return "\n".join(lines)


def deterministic_fallback_summary(
    previous_summary: str | None,
    messages: Sequence[Message],
    *,
    max_chars: int = 3_000,
) -> str:
    sections: list[str] = ["Fallback session summary (LLM compression unavailable)."]
    if previous_summary:
        sections.extend(("Previous summary:", previous_summary.strip()))
    rendered = render_messages(messages)
    if rendered:
        sections.extend(("Compressed history:", rendered))
    combined = "\n".join(sections)
    if len(combined) <= max_chars:
        return combined
    # Preserve the newest information, which is usually the most relevant.
    marker = "…[OLDER CONTENT TRUNCATED]\n"
    return marker + combined[-(max_chars - len(marker)) :]


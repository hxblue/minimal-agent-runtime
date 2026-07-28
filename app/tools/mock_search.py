"""Deterministic local search used for repeatable demonstrations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.models import ToolContext
from app.tools.base import ToolDefinition


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=3, ge=1, le=5)


@dataclass(frozen=True, slots=True)
class SearchDocument:
    title: str
    summary: str
    url: str
    keywords: tuple[str, ...]


_DOCUMENTS = (
    SearchDocument(
        title="Agent Runtime Basics",
        summary=(
            "An Agent Runtime loops between an LLM decision, tool execution, "
            "and a final answer."
        ),
        url="mock://docs/agent-runtime",
        keywords=("agent", "runtime", "loop", "tool", "智能体", "循环"),
    ),
    SearchDocument(
        title="Tool Schema Guide",
        summary="Tool names, descriptions, and JSON Schema let a model construct validated calls.",
        url="mock://docs/tool-schema",
        keywords=("tool", "schema", "json", "function", "参数", "工具"),
    ),
    SearchDocument(
        title="Session Isolation",
        summary="Messages, todos, and summaries must always be scoped by session identifiers.",
        url="mock://docs/session-isolation",
        keywords=("session", "isolation", "todo", "会话", "隔离"),
    ),
    SearchDocument(
        title="SQLite Persistence",
        summary="SQLite stores application state in one local database file without a server.",
        url="mock://docs/sqlite",
        keywords=("sqlite", "database", "persistence", "数据库", "持久化"),
    ),
    SearchDocument(
        title="Context and Memory",
        summary="Older turns can be summarized while recent messages and tool pairs stay intact.",
        url="mock://docs/context-memory",
        keywords=("context", "memory", "summary", "上下文", "记忆", "摘要"),
    ),
)


def search_documents(query: str, limit: int) -> list[dict[str, str]]:
    normalized = query.strip().lower()
    terms = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", normalized)
    scored: list[tuple[int, int, SearchDocument]] = []
    for index, document in enumerate(_DOCUMENTS):
        haystack = " ".join(
            (document.title, document.summary, *document.keywords)
        ).lower()
        score = sum(haystack.count(term) for term in terms)
        if normalized and normalized in haystack:
            score += 5
        if score:
            scored.append((score, index, document))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"title": doc.title, "summary": doc.summary, "url": doc.url}
        for _score, _index, doc in scored[:limit]
    ]


async def _search_handler(arguments: BaseModel, _context: ToolContext) -> str:
    args = SearchArgs.model_validate(arguments)
    results = search_documents(args.query, args.limit)
    return json.dumps(
        {
            "query": args.query,
            "results": results,
            "message": None if results else "No matching mock documents were found.",
        },
        ensure_ascii=False,
    )


SEARCH_TOOL = ToolDefinition(
    name="search",
    description=(
        "Search a deterministic local knowledge set about Agent Runtime concepts. "
        "Use this when the user explicitly asks to search or look up these topics."
    ),
    arguments_model=SearchArgs,
    handler=_search_handler,
)

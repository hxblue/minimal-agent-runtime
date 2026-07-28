"""Small SQLite repository used by the single-process interview demo."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from app.errors import RepositoryError
from app.models import (
    AgentRun,
    Message,
    Session,
    SessionMemory,
    TodoItem,
    ToolCall,
    TraceEvent,
    utc_now,
)


class SQLiteRepository:
    """Async-shaped repository backed by one serialized SQLite connection."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self._connection: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._lock:
            if self._connection is not None:
                return
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.database_path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_calls_json TEXT NOT NULL DEFAULT '[]',
                    tool_call_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session_seq
                    ON messages(session_id, seq);

                CREATE TABLE IF NOT EXISTS session_memories (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    through_message_id TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS todos (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_todos_session_seq
                    ON todos(session_id, seq);

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rounds INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_type TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_runs_session_started
                    ON agent_runs(session_id, started_at);

                CREATE TABLE IF NOT EXISTS trace_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    round_number INTEGER,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    duration_ms INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_trace_run_seq
                    ON trace_events(run_id, seq);
                """
            )
            connection.commit()
            self._connection = connection

    async def close(self) -> None:
        async with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _conn(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RepositoryError("repository is not initialized")
        return self._connection

    async def create_session(self, title: str | None = None) -> Session:
        session = Session(title=(title or "New session").strip() or "New session")
        async with self._lock:
            conn = self._conn()
            with conn:
                conn.execute(
                    "INSERT INTO sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (
                        session.id,
                        session.title,
                        session.created_at.isoformat(),
                        session.updated_at.isoformat(),
                    ),
                )
        return session

    async def list_sessions(self) -> list[Session]:
        async with self._lock:
            rows = self._conn().execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [self._session_from_row(row) for row in rows]

    async def get_session(self, session_id: str) -> Session | None:
        async with self._lock:
            row = self._conn().execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session_from_row(row) if row else None

    async def append_message(self, message: Message) -> None:
        tool_calls_json = json.dumps(
            [call.model_dump(mode="json") for call in message.tool_calls],
            ensure_ascii=False,
        )
        updated_at = utc_now().isoformat()
        async with self._lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO messages(
                            id, session_id, role, content, tool_calls_json,
                            tool_call_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            message.id,
                            message.session_id,
                            message.role,
                            message.content,
                            tool_calls_json,
                            message.tool_call_id,
                            message.created_at.isoformat(),
                        ),
                    )
                    conn.execute(
                        "UPDATE sessions SET updated_at = ? WHERE id = ?",
                        (updated_at, message.session_id),
                    )
            except sqlite3.IntegrityError as exc:
                raise RepositoryError("could not append message") from exc

    async def list_messages(self, session_id: str) -> list[Message]:
        async with self._lock:
            rows = self._conn().execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY seq", (session_id,)
            ).fetchall()
        return [self._message_from_row(row) for row in rows]

    async def get_memory(self, session_id: str) -> SessionMemory | None:
        async with self._lock:
            row = self._conn().execute(
                "SELECT * FROM session_memories WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return SessionMemory(
            session_id=row["session_id"],
            summary=row["summary"],
            through_message_id=row["through_message_id"],
            updated_at=row["updated_at"],
        )

    async def save_memory(self, memory: SessionMemory) -> None:
        async with self._lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO session_memories(
                            session_id, summary, through_message_id, updated_at
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT(session_id) DO UPDATE SET
                            summary = excluded.summary,
                            through_message_id = excluded.through_message_id,
                            updated_at = excluded.updated_at
                        """,
                        (
                            memory.session_id,
                            memory.summary,
                            memory.through_message_id,
                            memory.updated_at.isoformat(),
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise RepositoryError("could not save session memory") from exc

    async def add_todo(self, session_id: str, content: str) -> TodoItem:
        item = TodoItem(session_id=session_id, content=content.strip())
        async with self._lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO todos(id, session_id, content, completed, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            item.session_id,
                            item.content,
                            int(item.completed),
                            item.created_at.isoformat(),
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise RepositoryError("could not add todo") from exc
        return item

    async def list_todos(self, session_id: str) -> list[TodoItem]:
        async with self._lock:
            rows = self._conn().execute(
                "SELECT * FROM todos WHERE session_id = ? ORDER BY seq", (session_id,)
            ).fetchall()
        return [
            TodoItem(
                id=row["id"],
                session_id=row["session_id"],
                content=row["content"],
                completed=bool(row["completed"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def create_run(self, run: AgentRun) -> None:
        async with self._lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO agent_runs(
                            id, session_id, status, rounds, started_at, finished_at, error_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._run_values(run),
                    )
            except sqlite3.IntegrityError as exc:
                raise RepositoryError("could not create agent run") from exc

    async def update_run(self, run: AgentRun) -> None:
        async with self._lock:
            conn = self._conn()
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE agent_runs
                    SET status = ?, rounds = ?, finished_at = ?, error_type = ?
                    WHERE id = ?
                    """,
                    (
                        run.status,
                        run.rounds,
                        run.finished_at.isoformat() if run.finished_at else None,
                        run.error_type,
                        run.id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RepositoryError("agent run does not exist")

    async def get_run(self, run_id: str) -> AgentRun | None:
        async with self._lock:
            row = self._conn().execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return AgentRun(
            id=row["id"],
            session_id=row["session_id"],
            status=row["status"],
            rounds=row["rounds"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error_type=row["error_type"],
        )

    async def add_trace_event(self, event: TraceEvent) -> None:
        async with self._lock:
            conn = self._conn()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO trace_events(
                            id, run_id, session_id, round_number, event_type,
                            status, payload_json, duration_ms, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event.id,
                            event.run_id,
                            event.session_id,
                            event.round,
                            event.event_type,
                            event.status,
                            json.dumps(event.payload, ensure_ascii=False),
                            event.duration_ms,
                            event.created_at.isoformat(),
                        ),
                    )
            except sqlite3.IntegrityError as exc:
                raise RepositoryError("could not add trace event") from exc

    async def list_trace_events(self, run_id: str) -> list[TraceEvent]:
        async with self._lock:
            rows = self._conn().execute(
                "SELECT * FROM trace_events WHERE run_id = ? ORDER BY seq", (run_id,)
            ).fetchall()
        return [
            TraceEvent(
                id=row["id"],
                run_id=row["run_id"],
                session_id=row["session_id"],
                round=row["round_number"],
                event_type=row["event_type"],
                status=row["status"],
                payload=json.loads(row["payload_json"]),
                duration_ms=row["duration_ms"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            tool_calls=[
                ToolCall.model_validate(item)
                for item in json.loads(row["tool_calls_json"])
            ],
            tool_call_id=row["tool_call_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _run_values(run: AgentRun) -> tuple[object, ...]:
        return (
            run.id,
            run.session_id,
            run.status,
            run.rounds,
            run.started_at.isoformat(),
            run.finished_at.isoformat() if run.finished_at else None,
            run.error_type,
        )

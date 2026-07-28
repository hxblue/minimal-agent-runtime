"""Interactive terminal entry point sharing the same AgentApplication."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path

from app.bootstrap import build_resources
from app.config import Settings
from app.errors import SessionNotFoundError
from app.protocols import LLMClient

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


async def run_cli(
    settings: Settings,
    *,
    llm_client: LLMClient | None = None,
    input_fn: InputFunction = input,
    output_fn: OutputFunction = print,
) -> None:
    resources = await build_resources(settings, llm_client=llm_client)
    application = resources.application
    last_run_id: str | None = None
    try:
        sessions = await application.list_sessions()
        current = sessions[0] if sessions else await application.create_session("CLI Session")
        output_fn("Minimal Agent Runtime CLI")
        output_fn(f"Session: {current.title} ({current.id})")
        output_fn("Commands: /new /sessions /use /trace /tools /quit")
        while True:
            try:
                raw = input_fn("agent> ")
            except (EOFError, KeyboardInterrupt):
                output_fn("Session closed.")
                break
            text = raw.strip()
            if not text:
                continue
            if text == "/quit":
                output_fn("Session closed.")
                break
            if text.startswith("/new"):
                title = text.removeprefix("/new").strip() or "CLI Session"
                current = await application.create_session(title)
                output_fn(f"Created session: {current.title} ({current.id})")
                continue
            if text == "/sessions":
                for session in await application.list_sessions():
                    marker = "*" if session.id == current.id else " "
                    output_fn(f"{marker} {session.id}  {session.title}")
                continue
            if text.startswith("/use "):
                session_id = text.removeprefix("/use ").strip()
                try:
                    current = await application.get_session(session_id)
                except SessionNotFoundError:
                    output_fn(f"Session not found: {session_id}")
                else:
                    output_fn(f"Using session: {current.title} ({current.id})")
                continue
            if text == "/tools":
                for spec in application.list_tools():
                    function = spec["function"]
                    output_fn(f"- {function['name']}: {function['description']}")
                continue
            if text == "/trace":
                if last_run_id is None:
                    output_fn("No run has completed in this CLI session.")
                    continue
                for event in await application.get_trace(last_run_id):
                    output_fn(
                        f"[{event.status}] {event.event_type}"
                        + (f" round={event.round}" if event.round else "")
                    )
                continue
            if text.startswith("/"):
                output_fn(f"Unknown command: {text.split()[0]}")
                continue

            try:
                result = await application.run_agent(current.id, text)
            except ValueError as exc:
                output_fn(f"Input rejected: {exc}")
                continue
            last_run_id = result.run_id
            for event in result.events:
                if event.event_type == "tool_completed":
                    output_fn(
                        f"tool:{event.payload.get('tool_name')} "
                        f"status:{event.status} result:{event.payload.get('result')}"
                    )
            output_fn(f"agent: {result.final_answer}")
    finally:
        await resources.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Minimal Agent Runtime CLI")
    parser.add_argument(
        "--database-path",
        type=Path,
        help="Override AGENT_DATABASE_PATH for this CLI process.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    if args.database_path is not None:
        settings = settings.model_copy(update={"database_path": args.database_path})
    asyncio.run(run_cli(settings))


if __name__ == "__main__":
    main()

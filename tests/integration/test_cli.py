from __future__ import annotations

from app.cli import run_cli
from app.config import Settings
from app.models import LLMResponse, ToolCall
from tests.fakes import FakeLLMClient


class ScriptedInput:
    def __init__(self, commands: list[str]) -> None:
        self.commands = iter(commands)

    def __call__(self, _prompt: str) -> str:
        return next(self.commands)


async def test_cli_chat_tools_trace_and_commands(tmp_path) -> None:
    fake = FakeLLMClient(
        [
            LLMResponse(
                tool_calls=[
                    ToolCall(
                        id="calc",
                        name="calculator",
                        arguments_json='{"expression":"2+2"}',
                    )
                ]
            ),
            LLMResponse(final_text="4"),
        ]
    )
    output: list[str] = []
    await run_cli(
        Settings(database_path=tmp_path / "cli.db"),
        llm_client=fake,
        input_fn=ScriptedInput(
            ["/tools", "/sessions", "calculate 2+2", "/trace", "/new Second", "/quit"]
        ),
        output_fn=output.append,
    )
    rendered = "\n".join(output)
    assert "calculator" in rendered
    assert "tool:calculator status:succeeded" in rendered
    assert "agent: 4" in rendered
    assert "tool_completed" in rendered
    assert "Created session: Second" in rendered


async def test_cli_handles_unknown_session_and_command(tmp_path) -> None:
    output: list[str] = []
    await run_cli(
        Settings(database_path=tmp_path / "cli-errors.db"),
        llm_client=FakeLLMClient([]),
        input_fn=ScriptedInput(["/use missing", "/unknown", "/quit"]),
        output_fn=output.append,
    )
    rendered = "\n".join(output)
    assert "Session not found: missing" in rendered
    assert "Unknown command: /unknown" in rendered


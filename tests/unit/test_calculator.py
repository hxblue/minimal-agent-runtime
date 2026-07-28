from __future__ import annotations

import json

import pytest

from app.models import ToolCall, ToolContext
from app.tools.base import ToolRegistry
from app.tools.calculator import CALCULATOR_TOOL, evaluate_expression


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(18 + 24) * 3", 126),
        ("2 + 3 * 4", 14),
        ("-5 + 2", -3),
        ("7 / 2", 3.5),
        ("10 % 3", 1),
    ],
)
def test_evaluate_expression(expression: str, expected: int | float) -> None:
    assert evaluate_expression(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('whoami')",
        "(1).__class__",
        "values[0]",
        "2 ** 100",
        "1 / 0",
        "'text'",
    ],
)
def test_calculator_rejects_unsafe_or_unbounded_input(expression: str) -> None:
    with pytest.raises((ValueError, ZeroDivisionError)):
        evaluate_expression(expression)


async def test_calculator_runs_through_registry() -> None:
    registry = ToolRegistry()
    registry.register(CALCULATOR_TOOL)
    result = await registry.execute(
        ToolCall(
            name="calculator",
            arguments_json=json.dumps({"expression": "(18 + 24) * 3"}),
        ),
        ToolContext(session_id="s", run_id="r"),
    )
    assert result.ok
    assert "126" in result.content


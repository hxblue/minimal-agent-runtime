"""A bounded arithmetic calculator that never evaluates Python code."""

from __future__ import annotations

import ast
import math

from pydantic import BaseModel, ConfigDict, Field

from app.models import ToolContext
from app.tools.base import ToolDefinition


class CalculatorArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expression: str = Field(min_length=1, max_length=200)


_MAX_NODES = 64
_MAX_DEPTH = 12
_MAX_ABS_RESULT = 1e15
_MAX_EXPONENT = 12


def evaluate_expression(expression: str) -> int | float:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid arithmetic expression") from exc
    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        raise ValueError("expression is too complex")
    result = _evaluate(tree.body, depth=0)
    if not math.isfinite(float(result)) or abs(result) > _MAX_ABS_RESULT:
        raise ValueError("result is outside the safe range")
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


def _evaluate(node: ast.AST, *, depth: int) -> int | float:
    if depth > _MAX_DEPTH:
        raise ValueError("expression nesting is too deep")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise ValueError("only numeric constants are allowed")
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
        operand = _evaluate(node.operand, depth=depth + 1)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(
        node,
        ast.BinOp,
    ) and isinstance(node.op, ast.Add | ast.Sub | ast.Mult | ast.Div | ast.Mod | ast.Pow):
        left = _evaluate(node.left, depth=depth + 1)
        right = _evaluate(node.right, depth=depth + 1)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError("exponent is outside the safe range")
        result = _apply_binary(node.op, left, right)
        if not math.isfinite(float(result)) or abs(result) > _MAX_ABS_RESULT:
            raise ValueError("intermediate result is outside the safe range")
        return result
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def _apply_binary(
    operation: ast.operator, left: int | float, right: int | float
) -> int | float:
    if isinstance(operation, ast.Add):
        return left + right
    if isinstance(operation, ast.Sub):
        return left - right
    if isinstance(operation, ast.Mult):
        return left * right
    if isinstance(operation, ast.Div):
        return left / right
    if isinstance(operation, ast.Mod):
        return left % right
    result = left**right
    if isinstance(result, complex):
        raise ValueError("complex results are not supported")
    return result


async def _calculator_handler(arguments: BaseModel, _context: ToolContext) -> str:
    args = CalculatorArgs.model_validate(arguments)
    result = evaluate_expression(args.expression)
    return f"Calculation result: {result}"


CALCULATOR_TOOL = ToolDefinition(
    name="calculator",
    description=(
        "Evaluate a bounded arithmetic expression containing numbers, parentheses, "
        "and the operators +, -, *, /, %, or **."
    ),
    arguments_model=CalculatorArgs,
    handler=_calculator_handler,
)

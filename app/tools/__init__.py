"""Built-in tool registration."""

from app.protocols import SessionRepository
from app.tools.base import ToolRegistry
from app.tools.calculator import CALCULATOR_TOOL
from app.tools.mock_search import SEARCH_TOOL
from app.tools.todo import create_todo_tool
from app.tools.weather import WEATHER_TOOL


def build_tool_registry(
    repository: SessionRepository, *, result_max_chars: int = 4_000
) -> ToolRegistry:
    registry = ToolRegistry(result_max_chars=result_max_chars)
    registry.register(CALCULATOR_TOOL)
    registry.register(SEARCH_TOOL)
    registry.register(create_todo_tool(repository))
    registry.register(WEATHER_TOOL)
    return registry


__all__ = ["ToolRegistry", "build_tool_registry"]


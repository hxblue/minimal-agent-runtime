"""Deterministic mock weather tool for repeatable demonstrations."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ToolContext
from app.tools.base import ToolDefinition


class WeatherArgs(BaseModel):
    """Arguments accepted by the weather tool."""

    model_config = ConfigDict(extra="forbid", strict=True)

    city: str = Field(min_length=1, max_length=100)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        city = value.strip()
        if not city:
            raise ValueError("city must not be empty")
        return city


@dataclass(frozen=True, slots=True)
class WeatherRecord:
    condition: str
    temperature_c: int
    humidity_percent: int


_WEATHER_DATA: dict[str, WeatherRecord] = {
    "广州": WeatherRecord(
        condition="多云",
        temperature_c=29,
        humidity_percent=74,
    ),
    "北京": WeatherRecord(
        condition="晴",
        temperature_c=26,
        humidity_percent=42,
    ),
    "上海": WeatherRecord(
        condition="小雨",
        temperature_c=27,
        humidity_percent=81,
    ),
    "深圳": WeatherRecord(
        condition="阵雨",
        temperature_c=28,
        humidity_percent=79,
    ),
}


async def _weather_handler(
    arguments: BaseModel,
    _context: ToolContext,
) -> str:
    """Look up weather data for one city."""

    args = WeatherArgs.model_validate(arguments)
    weather = _WEATHER_DATA.get(args.city)

    if weather is None:
        return json.dumps(
            {
                "found": False,
                "city": args.city,
                "message": "No mock weather data is available for this city.",
                "source": "mock-weather",
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "found": True,
            "city": args.city,
            "condition": weather.condition,
            "temperature_c": weather.temperature_c,
            "humidity_percent": weather.humidity_percent,
            "source": "mock-weather",
        },
        ensure_ascii=False,
    )


WEATHER_TOOL = ToolDefinition(
    name="weather",
    description=(
        "Look up deterministic mock weather information for a city. "
        "Use this tool when the user asks about weather, temperature, "
        "or humidity in a supported city."
    ),
    arguments_model=WeatherArgs,
    handler=_weather_handler,
)
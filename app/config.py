"""Environment-backed application settings with secret-safe representations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Settings(BaseModel):
    """Validated runtime settings.

    Missing LLM credentials do not prevent the application from starting. They
    are checked only when a real model run is requested.
    """

    model_config = ConfigDict(extra="forbid")

    app_name: str = "Minimal Agent Runtime"
    database_path: Path = Path("data/agent.db")
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_connect_timeout_seconds: float = Field(default=10.0, gt=0, le=120)
    llm_read_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    llm_temperature: float = Field(default=0.0, ge=0, le=2)
    max_rounds: int = Field(default=6, ge=1, le=20)
    context_budget: int = Field(default=12_000, ge=1_000, le=1_000_000)
    compression_threshold: float = Field(default=0.75, ge=0.5, le=0.95)
    recent_turns: int = Field(default=4, ge=1, le=20)
    tool_result_max_chars: int = Field(default=4_000, ge=200, le=50_000)
    trace_value_max_chars: int = Field(default=500, ge=50, le=10_000)
    user_input_max_chars: int = Field(default=20_000, ge=100, le=200_000)
    system_prompt: str = (
        "You are a concise assistant. Use registered tools when they are needed. "
        "Never invent tool results. After receiving tool results, answer the user clearly."
    )

    @field_validator("llm_base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            raise ValueError("LLM_BASE_URL must use http:// or https://")
        return value

    @field_validator("llm_model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return value.strip()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        if env is None:
            load_dotenv()
        source = os.environ if env is None else env

        def optional_secret(name: str) -> SecretStr | None:
            value = source.get(name, "").strip()
            return SecretStr(value) if value else None

        return cls(
            database_path=Path(source.get("AGENT_DATABASE_PATH", "data/agent.db")),
            llm_base_url=source.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_model=source.get("LLM_MODEL", ""),
            llm_api_key=optional_secret("LLM_API_KEY"),
            llm_connect_timeout_seconds=float(
                source.get("LLM_CONNECT_TIMEOUT_SECONDS", "10")
            ),
            llm_read_timeout_seconds=float(source.get("LLM_READ_TIMEOUT_SECONDS", "60")),
            llm_temperature=float(source.get("LLM_TEMPERATURE", "0")),
            max_rounds=int(source.get("AGENT_MAX_ROUNDS", "6")),
            context_budget=int(source.get("AGENT_CONTEXT_BUDGET", "12000")),
            compression_threshold=float(
                source.get("AGENT_COMPRESSION_THRESHOLD", "0.75")
            ),
            recent_turns=int(source.get("AGENT_RECENT_TURNS", "4")),
        )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_model and self.llm_api_key)

    def api_key_value(self) -> str:
        return self.llm_api_key.get_secret_value() if self.llm_api_key else ""

"""HTTP request and health response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionRequest(APIModel):
    title: str | None = Field(default=None, max_length=200)


class RunRequest(APIModel):
    text: str = Field(min_length=1, max_length=20_000)


class HealthResponse(APIModel):
    status: str
    llm_configured: bool
    storage: str
    version: str


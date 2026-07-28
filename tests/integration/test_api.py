from __future__ import annotations

from contextlib import asynccontextmanager

import httpx

from app.api.app import create_app
from app.config import Settings
from app.errors import LLMTimeoutError
from app.models import LLMResponse, ToolCall
from tests.fakes import FakeLLMClient


@asynccontextmanager
async def api_client(app):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client


async def test_api_session_run_history_trace_and_tools(tmp_path) -> None:
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
            LLMResponse(final_text="The result is 4"),
        ]
    )
    app = create_app(
        Settings(database_path=tmp_path / "api.db"),
        llm_client=fake,
    )
    async with api_client(app) as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["llm_configured"] is True

        created = await client.post("/api/sessions", json={"title": "API Test"})
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert (await client.get("/api/sessions")).json()[0]["id"] == session_id

        run = await client.post(
            f"/api/sessions/{session_id}/runs",
            json={"text": "calculate 2+2"},
        )
        assert run.status_code == 200
        result = run.json()
        assert result["status"] == "completed"
        assert any(event["event_type"] == "tool_completed" for event in result["events"])

        history = (await client.get(f"/api/sessions/{session_id}/messages")).json()
        assert [message["role"] for message in history] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]
        trace = await client.get(f"/api/runs/{result['run_id']}/trace")
        assert trace.status_code == 200
        assert trace.json()[-1]["event_type"] == "run_completed"
        tools = (await client.get("/api/tools")).json()
        assert [tool["function"]["name"] for tool in tools] == [
            "calculator",
            "search",
            "todo",
            "weather",
        ]


async def test_api_validation_and_not_found_responses(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "validation.db"),
        llm_client=FakeLLMClient([LLMResponse(final_text="unused")]),
    )
    async with api_client(app) as client:
        assert (
            await client.post("/api/sessions", json={"title": "x" * 201})
        ).status_code == 422
        assert (
            await client.post("/api/sessions/missing/runs", json={"text": "hi"})
        ).status_code == 404
        assert (
            await client.post("/api/sessions/missing/runs", json={"text": ""})
        ).status_code == 422
        assert (await client.get("/api/runs/missing/trace")).status_code == 404


async def test_api_rejects_input_larger_than_runtime_context_allowance(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "oversized.db", context_budget=4_000),
        llm_client=FakeLLMClient([LLMResponse(final_text="must not be called")]),
    )
    async with api_client(app) as client:
        session_id = (await client.post("/api/sessions", json={})).json()["id"]
        response = await client.post(
            f"/api/sessions/{session_id}/runs",
            json={"text": "x" * 1_001},
        )
        assert response.status_code == 422


async def test_api_returns_controlled_failed_run_without_secret(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "failure.db"),
        llm_client=FakeLLMClient([LLMTimeoutError("secret upstream detail")]),
    )
    async with api_client(app) as client:
        session_id = (await client.post("/api/sessions", json={})).json()["id"]
        response = await client.post(
            f"/api/sessions/{session_id}/runs",
            json={"text": "hello"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert "secret upstream detail" not in response.text

from __future__ import annotations

import httpx

from app.api.app import create_app
from app.config import Settings
from app.models import LLMResponse
from tests.fakes import FakeLLMClient


async def test_web_assets_and_api_routes_are_served(tmp_path) -> None:
    app = create_app(
        Settings(database_path=tmp_path / "web.db"),
        llm_client=FakeLLMClient([LLMResponse(final_text="Hello")]),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            index = await client.get("/")
            css = await client.get("/static/styles.css")
            javascript = await client.get("/static/app.js")
            health = await client.get("/api/health")
        assert index.status_code == css.status_code == javascript.status_code == 200
        assert "Runtime Workbench" in index.text
        assert "--cobalt" in css.text
        assert "loadHealthAndTools" in javascript.text
        assert health.headers["content-type"].startswith("application/json")

"""FastAPI application factory and resource lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.bootstrap import build_resources
from app.config import Settings
from app.protocols import LLMClient


def create_app(
    settings: Settings | None = None,
    *,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resources = await build_resources(resolved_settings, llm_client=llm_client)
        app.state.resources = resources
        try:
            yield
        finally:
            await resources.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    web_directory = Path(__file__).resolve().parent.parent / "web"
    application.mount(
        "/static",
        StaticFiles(directory=web_directory),
        name="static",
    )

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(web_directory / "index.html")

    return application


app = create_app()

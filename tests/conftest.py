from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio

from app.storage.sqlite import SQLiteRepository


@pytest_asyncio.fixture
async def repository(tmp_path) -> AsyncIterator[SQLiteRepository]:
    repo = SQLiteRepository(tmp_path / "agent-test.db")
    await repo.initialize()
    try:
        yield repo
    finally:
        await repo.close()


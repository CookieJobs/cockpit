"""pytest fixtures for Cockpit。"""
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from app.core import storage


@pytest_asyncio.fixture
async def temp_db() -> AsyncIterator[str]:
    """每个测试一个临时 SQLite 数据库。"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    url = f"sqlite+aiosqlite:///{db_path}"
    storage.reset_engine()
    storage.init_engine(database_url=url)
    await storage.create_tables()
    try:
        yield url
    finally:
        await storage.drop_tables()
        storage.reset_engine()
        Path(db_path).unlink(missing_ok=True)

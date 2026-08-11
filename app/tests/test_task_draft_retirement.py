"""Phase 2 regressions for retiring the task draft state without data loss."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.api.tasks import router as task_router
from app.core import storage
from app.llm.tools import TOOLS
from app.mcp_server import _handle_list_tools


def _create_legacy_tasks_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                archived BOOLEAN NOT NULL DEFAULT 0,
                created_at DATE NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                due DATE,
                blocked BOOLEAN NOT NULL DEFAULT 0,
                draft BOOLEAN NOT NULL DEFAULT 0,
                completed_at DATE,
                checklist_json TEXT NOT NULL DEFAULT '[]',
                created_at DATE NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO projects (id, name, created_at) VALUES ('proj_1', '迁移项目', '2026-08-11');
            INSERT INTO tasks (
                id, project_id, title, status, priority, draft, created_at
            ) VALUES ('task_1', 'proj_1', '保留任务', '未开始', 'P2', 1, '2026-08-11');
            """
        )


@pytest.mark.asyncio
async def test_draft_column_migration_keeps_rows_as_unfinished_tasks(tmp_path: Path):
    db_path = tmp_path / "legacy-cockpit.db"
    _create_legacy_tasks_table(db_path)
    storage.reset_engine()
    storage.init_engine(database_url=f"sqlite+aiosqlite:///{db_path}")
    try:
        backup = await storage.run_schema_migrations()
        assert backup is not None and backup.exists()

        with sqlite3.connect(db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
            row = connection.execute(
                "SELECT title, status FROM tasks WHERE id = 'task_1'"
            ).fetchone()

        assert "draft" not in columns
        assert row == ("保留任务", "未开始")
        assert await storage.run_schema_migrations() is None
    finally:
        storage.reset_engine()


@pytest.mark.asyncio
async def test_task_api_tools_and_mcp_no_longer_expose_draft():
    assert "/confirm-drafts" not in {route.path for route in task_router.routes}
    assert "confirm_drafts" not in {tool["name"] for tool in TOOLS}
    assert "draft" not in str(TOOLS)

    listed = await _handle_list_tools()
    list_tasks = next(tool for tool in listed.tools if tool.name == "list_tasks")
    assert "draft" not in str(list_tasks.input_schema)

"""P0 sentinels: formal output must never include unconfirmed achievements."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate
from app.llm.tools import tool_generate_weekly_report


REPORT_PAGE = Path(__file__).parent.parent.parent / "web" / "app" / "report" / "page.tsx"


@pytest.mark.asyncio
async def test_formal_weekly_report_reads_only_ready_achievements(temp_db):
    project = await storage.add_project(ProjectCreate(name="输出边界"))
    ready_task = await storage.add_task(TaskCreate(project=project.id, title="ready"))
    needs_task = await storage.add_task(TaskCreate(project=project.id, title="needs"))
    pending_task = await storage.add_task(TaskCreate(project=project.id, title="pending"))

    await storage.complete_task(
        ready_task.id,
        outcome="完成 READY_SENTINEL 并通过验收验证",
        cv="完成 READY_SENTINEL 并通过验收验证",
        cv_status=CVStatus.READY,
        confirmed_cv=True,
    )
    await storage.complete_task(
        needs_task.id,
        outcome="完成 NEEDS_DATA_SENTINEL 并等待证据补充",
        cv="完成 NEEDS_DATA_SENTINEL 并等待证据补充",
        cv_status=CVStatus.NEEDS_DATA,
    )
    await storage.complete_task(
        pending_task.id,
        outcome="完成 PENDING_SENTINEL 并暂存待整理",
        cv="完成 PENDING_SENTINEL 并暂存待整理",
        cv_status=CVStatus.PENDING,
    )

    report = await tool_generate_weekly_report()
    ready = await storage.list_output_ready_achievements(since=date.today())

    assert "READY_SENTINEL" in report
    assert "NEEDS_DATA_SENTINEL" not in report
    assert "PENDING_SENTINEL" not in report
    assert [item.cv for item in ready] == ["完成 READY_SENTINEL 并通过验收验证"]


def test_report_page_uses_a_ready_only_collection_for_markdown_and_keeps_recovery_separate():
    source = REPORT_PAGE.read_text(encoding="utf-8")

    assert "only_ready: true" in source
    assert "generateReport(readyItems" in source
    assert "recoveryItems" in source

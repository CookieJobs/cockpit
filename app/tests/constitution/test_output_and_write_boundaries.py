"""L2 tests for evidence-grounded achievement write and output boundaries."""

from pathlib import Path

import pytest

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate


@pytest.mark.asyncio
async def test_incomplete_completion_never_becomes_ready(temp_db) -> None:
    project = await storage.add_project(ProjectCreate(name="宪法测试"))
    task = await storage.add_task(TaskCreate(project=project.id, title="发布登录优化"))

    achievement = await storage.complete_task(
        task.id,
        outcome="已完成",
        cv="完成「发布登录优化」",
        cv_status=CVStatus.READY,
    )

    assert achievement is not None
    assert achievement.cv_status is CVStatus.NEEDS_DATA


def test_formal_output_uses_ready_assets_only() -> None:
    source = (Path(__file__).parents[3] / "web" / "lib" / "templates.ts").read_text(encoding="utf-8")

    assert 'match: (a) => a.cv_status === "ready"' in source
    assert 'a.cv_status === "ready" || a.cv_status === "needs_data"' not in source


def test_achievement_api_forbids_direct_status_override() -> None:
    source = (Path(__file__).parents[2] / "core" / "models.py").read_text(encoding="utf-8")

    update_block = source.split("class AchievementUpdate", 1)[1].split("class Achievement", 1)[0]
    assert "cv_status" not in update_block
    assert 'ConfigDict(extra="forbid"' in update_block

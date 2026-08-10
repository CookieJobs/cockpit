from __future__ import annotations

import pytest

from app.core import storage
from app.core.models import AchievementUpdate, ProjectCreate, TaskCreate
from app.harness.feedback import get_latest_feedback


@pytest.mark.asyncio
async def test_cv_edit_records_feedback_when_achievement_has_trace(temp_db) -> None:
    project = await storage.add_project(ProjectCreate(name="Harness"))
    task = await storage.add_task(TaskCreate(project=project.id, title="登录优化"))
    achievement = await storage.complete_task(
        task.id,
        outcome="优化登录流程",
        cv="优化登录流程",
        distillation_trace_id="trace_test",
    )
    assert achievement is not None

    updated = await storage.update_achievement_cv(
        achievement.id, AchievementUpdate(cv="优化登录流程，降低耗时")
    )

    assert updated is not None
    feedback = await get_latest_feedback()
    assert feedback is not None
    assert feedback.trace_id == "trace_test"
    assert feedback.edit_type == "minor_edit"

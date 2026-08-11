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


@pytest.mark.asyncio
async def test_initial_confirmed_candidate_records_direct_accept_feedback(temp_db) -> None:
    project = await storage.add_project(ProjectCreate(name="Harness"))
    task = await storage.add_task(TaskCreate(project=project.id, title="登录优化"))

    achievement = await storage.complete_task(
        task.id,
        outcome="修复登录鉴权问题并恢复 20 名用户的正常访问",
        cv="修复登录鉴权问题，恢复 20 名用户登录",
        distillation_trace_id="trace_initial_confirmation",
        confirmed_cv=True,
    )

    assert achievement is not None
    feedback = await get_latest_feedback()
    assert feedback is not None
    assert feedback.trace_id == "trace_initial_confirmation"
    assert feedback.edit_type == "direct_accept"


@pytest.mark.asyncio
async def test_resolve_confirmation_records_light_edit_feedback(temp_db) -> None:
    project = await storage.add_project(ProjectCreate(name="Harness"))
    task = await storage.add_task(TaskCreate(project=project.id, title="登录优化"))
    achievement = await storage.complete_task(
        task.id,
        outcome="修复登录鉴权问题并恢复受影响用户的正常访问",
        cv="修复登录鉴权问题，恢复用户登录",
        follow_up_questions=["恢复了多少用户？"],
        distillation_trace_id="trace_resolve_confirmation",
    )

    resolved = await storage.resolve_achievement(
        achievement.id,
        answers={"0": "恢复了 20 名用户登录"},
        cv="修复登录鉴权问题，恢复 20 名用户登录",
    )

    assert resolved is not None
    feedback = await get_latest_feedback()
    assert feedback is not None
    assert feedback.trace_id == "trace_resolve_confirmation"
    assert feedback.edit_type == "light_edit"

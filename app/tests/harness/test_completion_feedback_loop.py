"""Confirmation feedback is trace-linked, local, and idempotent on retry."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate


@pytest.mark.asyncio
async def test_first_confirmation_records_candidate_to_final_once_even_if_client_retries(temp_db):
    project = await storage.add_project(ProjectCreate(name="Feedback"))
    task = await storage.add_task(TaskCreate(project=project.id, title="登录鉴权修复"))
    achievement = await storage.complete_task(
        task.id,
        outcome="修复登录鉴权并恢复 20 名用户访问",
        cv="修复登录鉴权问题，恢复用户访问",
        follow_up_questions=["恢复多少用户？"],
        distillation_trace_id="trace_confirmation_once",
    )
    assert achievement is not None

    final_cv = "修复登录鉴权问题，恢复 20 名用户正常访问"
    resolved = await storage.resolve_achievement(
        achievement.id, answers={"0": "20 名"}, cv=final_cv,
    )
    retry = await storage.resolve_achievement(
        achievement.id, answers={"0": "20 名"}, cv=final_cv,
    )

    assert resolved is not None and retry is not None
    async with storage.get_session() as session:
        rows = (await session.execute(
            select(storage.DistillationFeedbackORM).where(
                storage.DistillationFeedbackORM.trace_id == "trace_confirmation_once"
            )
        )).scalars().all()
    confirmations = [row for row in rows if json.loads(row.diff_json).get("action") == "confirmed"]
    assert len(confirmations) == 1
    assert confirmations[0].original_cv == "修复登录鉴权问题，恢复用户访问"
    assert confirmations[0].final_cv == final_cv
    assert confirmations[0].edit_type == "light_edit"

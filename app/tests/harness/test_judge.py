from __future__ import annotations

import pytest

from app.harness.adapter import FakeAdapter
from app.harness.judge import FakeJudge
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)
from app.harness.report import summarize
from app.harness.runner import run_cases


@pytest.mark.asyncio
async def test_runner_includes_strict_judge_semantic_scores() -> None:
    case = AchievementDistillationCase(
        id="judge_case", category="golden", severity="p0",
        input=AchievementDistillationInput(task_title="登录优化", outcome="支付成功率提升15%", language="zh-CN"),
    )
    adapter = FakeAdapter({case.id: AchievementDistillationOutput(cv="优化登录流程，提升支付成功率15%", generator_status="polished")})
    judge = FakeJudge({case.id: '{"score":4,"violations":[],"suggestions":[],"semantic_scores":{"impact_clarity":4,"specificity":4,"authenticity":4,"resume_usefulness":4,"follow_up_usefulness":4}}'})
    report = summarize(await run_cases([case], adapter, judge=judge))
    assert report.results[0].judge.score == 4
    assert report.semantic_average == 4

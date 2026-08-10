from __future__ import annotations

import pytest
from app.harness.adapter import FakeAdapter
from app.harness.judge import CurrentLLMJudge, FakeJudge, build_current_judge, parse_judge_output
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)
from app.harness.report import summarize
from app.harness.runner import run_cases
from app.llm.base import LLMResponse


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


def test_judge_accepts_calibrated_four_dimension_contract() -> None:
    judge, scores = parse_judge_output(
        '{"scores":{"authenticity":4,"impact_clarity":3,"resume_usefulness":4,"follow_up_usefulness":5},'
        '"violations":[],"reason":"grounded","suggestions":[]}'
    )

    assert judge.reason == "grounded"
    assert scores.authenticity == 4


@pytest.mark.asyncio
async def test_current_llm_judge_sends_only_case_and_generated_output() -> None:
    class Client:
        async def chat(self, messages, system, tools=None):
            assert tools is None
            assert "用户事实" in messages[0]["content"]
            assert "生成 CV" in messages[0]["content"]
            assert "不要判定数字" in system
            assert "无需追问" in system
            return LLMResponse(text='{"scores":{"authenticity":4,"impact_clarity":3,"resume_usefulness":4,"follow_up_usefulness":5},"violations":[],"reason":"grounded","suggestions":[]}')

    case = AchievementDistillationCase(
        id="judge_current", category="golden", severity="p0",
        input=AchievementDistillationInput(task_title="登录优化", outcome="支付成功率提升15%", language="zh-CN"),
    )
    output = AchievementDistillationOutput(cv="优化登录流程，支付成功率提升15%", generator_status="polished")

    raw = await CurrentLLMJudge(Client()).judge(case, output)

    assert '"authenticity":4' in raw


def test_current_judge_is_skipped_without_a_configured_client() -> None:
    assert build_current_judge(None) is None

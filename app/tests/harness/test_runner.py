from __future__ import annotations

from typing import Literal

import pytest
from app.harness.adapter import FakeAdapter, PolishCvAdapter
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)
from app.harness.runner import run_cases


def make_case(
    case_id: str,
    *,
    category: Literal["golden", "boundary", "adversarial"] = "golden",
    outcome: str = "优化支付流程，成功率提升 15%",
) -> AchievementDistillationCase:
    return AchievementDistillationCase(
        id=case_id,
        category=category,
        input=AchievementDistillationInput(task_title="优化支付流程", outcome=outcome, language="zh"),
        expected={},
        forbidden=[],
        severity="p0",
    )


@pytest.mark.asyncio
async def test_runner_preserves_case_order_and_generator_status() -> None:
    first = make_case("golden_001")
    second = make_case("golden_002")
    adapter = FakeAdapter(
        {
            "golden_001": AchievementDistillationOutput(
                cv="优化支付流程，成功率提升 15%",
                follow_up_questions=[],
                generator_status="polished",
            ),
            "golden_002": AchievementDistillationOutput(
                cv="优化支付流程，成功率提升 15%",
                follow_up_questions=[],
                generator_status="fallback",
            ),
        }
    )

    results = await run_cases([first, second], adapter)

    assert [result.case_id for result in results] == ["golden_001", "golden_002"]
    assert results[0].output.generator_status == "polished"
    assert results[1].output.generator_status == "fallback"
    assert adapter.calls == ["golden_001", "golden_002"]


@pytest.mark.asyncio
async def test_runner_marks_forbidden_output_as_failed() -> None:
    case = make_case("boundary_number", category="boundary", outcome="优化支付流程")
    case.forbidden = ["30%"]
    adapter = FakeAdapter(
        {
            "boundary_number": AchievementDistillationOutput(
                cv="优化支付流程，成功率提升 30%",
                follow_up_questions=[],
                generator_status="polished",
            )
        }
    )

    result = (await run_cases([case], adapter))[0]

    assert result.passed is False
    assert result.hard_checks.has_unsupported_number is True
    assert "forbidden:30%" in result.judge.violations


@pytest.mark.asyncio
async def test_polish_adapter_maps_unpolished_response_to_fallback() -> None:
    async def fake_call(task_title: str, outcome: str) -> tuple[str, bool, list[str]]:
        assert task_title == "优化支付流程"
        assert outcome == "支付结果待补"
        return "完成「优化支付流程」", False, []

    output = await PolishCvAdapter(call=fake_call).generate(
        AchievementDistillationInput(
            task_title="优化支付流程",
            outcome="支付结果待补",
            language="zh",
        )
    )

    assert output.generator_status == "fallback"

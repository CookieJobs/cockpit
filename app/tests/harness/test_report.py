from __future__ import annotations

from app.harness.models import (
    AchievementDistillationOutput,
    EvaluationResult,
    HardChecks,
    JudgeResult,
    SemanticScores,
)
from app.harness.report import summarize


def make_result(case_id: str, *, category: str, passed: bool) -> EvaluationResult:
    return EvaluationResult(
        case_id=case_id,
        category=category,
        output=AchievementDistillationOutput(
            cv="优化支付流程，成功率提升 15%",
            follow_up_questions=[],
            generator_status="polished",
        ),
        hard_checks=HardChecks(
            schema_valid=True,
            length_valid=True,
            has_strong_action=True,
            has_unsupported_number=not passed,
            has_unsupported_entity=False,
            likely_duplicate_outcome=False,
            likely_overclaim=not passed,
            ownership_violation=False,
        ),
        semantic_scores=SemanticScores(),
        judge=JudgeResult(violations=["unsupported number"] if not passed else []),
        passed=passed,
    )


def test_report_contains_category_rates_and_ordered_failures() -> None:
    report = summarize(
        [
            make_result("golden_001", category="golden", passed=True),
            make_result("boundary_001", category="boundary", passed=False),
        ]
    )

    assert report.total == 2
    assert report.by_category["golden"].passed == 1
    assert report.by_category["golden"].pass_rate == 1.0
    assert report.by_category["boundary"].passed == 0
    assert report.failures[0].case_id == "boundary_001"
    assert report.p0_violation_counts["unsupported_numbers"] == 1

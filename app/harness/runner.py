"""Deterministic offline execution for achievement-distillation cases."""

from __future__ import annotations

import json

from app.harness.adapter import CaseAwareAdapter, DistillationAdapter
from app.harness.l1 import evaluate_l1, is_l1_pass
from app.harness.judge import JudgeAdapter, parse_judge_output
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationOutput,
    EvaluationResult,
    JudgeResult,
    SemanticScores,
)


def _case_violations(case: AchievementDistillationCase, cv: str) -> list[str]:
    return [f"forbidden:{item}" for item in case.forbidden if item and item in cv]


async def _generate(
    case: AchievementDistillationCase,
    adapter: DistillationAdapter,
) -> AchievementDistillationOutput:
    if isinstance(adapter, CaseAwareAdapter):
        return await adapter.generate_case(case)
    return await adapter.generate(case.input)


async def run_cases(
    cases: list[AchievementDistillationCase],
    adapter: DistillationAdapter,
    judge: JudgeAdapter | None = None,
) -> list[EvaluationResult]:
    """Run cases in supplied order and preserve every L1/fixture failure."""
    results: list[EvaluationResult] = []
    for case in cases:
        output = await _generate(case, adapter)
        hard_checks = evaluate_l1(case, output)
        violations = _case_violations(case, output.cv)
        judge_result = JudgeResult(violations=violations)
        semantic_scores = SemanticScores()
        if judge is not None:
            try:
                judge_result, semantic_scores = parse_judge_output(await judge.judge(case, output))
                judge_result.violations = [*violations, *judge_result.violations]
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                judge_result = JudgeResult(violations=[*violations, f"judge_parse_failed:{type(exc).__name__}"])
        passed = is_l1_pass(hard_checks) and not violations
        results.append(
            EvaluationResult(
                case_id=case.id,
                category=case.category,
                output=output,
                hard_checks=hard_checks,
                semantic_scores=semantic_scores,
                judge=judge_result,
                passed=passed,
            )
        )
    return results

"""Deterministic offline execution for achievement-distillation cases."""

from __future__ import annotations

import json

from app.harness.adapter import CaseAwareAdapter, DistillationAdapter
from app.harness.judge import JudgeAdapter, parse_judge_output
from app.harness.l1 import evaluate_l1
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationOutput,
    EvaluationResult,
    JudgeResult,
    SemanticScores,
)


def _case_violations(case: AchievementDistillationCase, cv: str) -> list[str]:
    return [f"forbidden:{item}" for item in case.forbidden if item and item in cv]


def _failure_reasons(hard_checks, forbidden: list[str], semantic_scores: SemanticScores) -> list[str]:
    """Map every failed deterministic or semantic condition to a stable reason."""
    reasons: list[str] = []
    if not hard_checks.length_valid:
        reasons.append("invalid_length")
    if not hard_checks.follow_up_count_valid:
        reasons.append("too_many_follow_ups")
    if hard_checks.has_unsupported_number:
        reasons.append("unsupported_number")
    if hard_checks.has_unsupported_entity:
        reasons.append("unsupported_entity")
    if hard_checks.ownership_violation:
        reasons.append("ownership_overclaim")
    if hard_checks.likely_duplicate_outcome:
        reasons.append("duplicate_outcome")
    if hard_checks.generator_is_fallback:
        reasons.append("generator_fallback")
    if hard_checks.generator_is_parse_failed:
        reasons.append("generator_parse_failed")
    if forbidden:
        reasons.append("forbidden_output")
    for field, reason in (
        ("authenticity", "semantic_authenticity_below_threshold"),
        ("impact_clarity", "semantic_impact_clarity_below_threshold"),
        ("resume_usefulness", "semantic_resume_usefulness_below_threshold"),
        ("follow_up_usefulness", "semantic_follow_up_usefulness_below_threshold"),
    ):
        value = getattr(semantic_scores, field)
        if value is not None and value < 3:
            reasons.append(reason)
    return reasons


def _attribute(case: AchievementDistillationCase, reasons: list[str], hard_checks) -> tuple[str | None, str]:
    if "current_baseline" not in case.suites and case.target_capabilities:
        return "capability_gap", f"Current polish_cv does not expose: {', '.join(case.target_capabilities)}."
    if not reasons and "current_baseline" in case.suites:
        if not hard_checks.has_strong_action:
            return "evaluator_false_negative", "Legacy strong-action whitelist rejected an otherwise valid current output."
        return None, ""
    if any(reason in reasons for reason in ("generator_fallback", "generator_parse_failed", "unsupported_number", "unsupported_entity", "ownership_overclaim", "forbidden_output")):
        return "generator_failure", "The generated response breached a current safety or output requirement."
    if any(reason.startswith("semantic_") for reason in reasons):
        return "ambiguous", "A semantic quality judgement requires human or LLM review."
    return "generator_failure", "The current capability did not meet a deterministic output requirement."


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
        failure_reasons = _failure_reasons(hard_checks, violations, semantic_scores)
        if "current_baseline" not in case.suites and case.target_capabilities and not failure_reasons:
            failure_reasons.append("capability_gap")
        passed = not failure_reasons
        attribution, attribution_reason = _attribute(case, failure_reasons, hard_checks)
        results.append(
            EvaluationResult(
                case_id=case.id,
                category=case.category,
                suites=case.suites,
                output=output,
                hard_checks=hard_checks,
                semantic_scores=semantic_scores,
                judge=judge_result,
                passed=passed,
                failure_reasons=failure_reasons,
                attribution=attribution,
                attribution_reason=attribution_reason,
            )
        )
    return results

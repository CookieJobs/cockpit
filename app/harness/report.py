"""Stable JSON-serializable aggregation for harness runs."""

from __future__ import annotations

from collections import Counter

from app.harness.models import CategorySummary, EvaluationResult, FailureSummary, HarnessReport


def summarize(results: list[EvaluationResult]) -> HarnessReport:
    categories = ("golden", "boundary", "adversarial")
    by_category: dict[str, CategorySummary] = {}
    for category in categories:
        category_results = [result for result in results if result.category == category]
        passed = sum(result.passed for result in category_results)
        total = len(category_results)
        by_category[category] = CategorySummary(
            total=total,
            passed=passed,
            pass_rate=passed / total if total else 0.0,
        )

    p0 = Counter[str]()
    status = Counter[str]()
    attribution_counts = Counter[str]()
    failures: list[FailureSummary] = []
    for result in results:
        checks = result.hard_checks
        status[result.output.generator_status] += 1
        if result.attribution:
            attribution_counts[result.attribution] += 1
        if checks.has_unsupported_number:
            p0["unsupported_numbers"] += 1
        if checks.has_unsupported_entity:
            p0["unsupported_entities"] += 1
        if checks.ownership_violation:
            p0["ownership_violations"] += 1
        if not checks.schema_valid:
            p0["schema_invalid"] += 1
        if not result.passed:
            failures.append(
                FailureSummary(
                    case_id=result.case_id,
                    category=result.category,
                    violations=[
                        *result.judge.violations,
                        *result.hard_checks.unsupported_numbers,
                        *result.hard_checks.unsupported_entities,
                    ],
                    failure_reasons=result.failure_reasons,
                    attribution=result.attribution,
                )
            )

    passed = sum(result.passed for result in results)
    total = len(results)
    semantic_values = [
        score
        for result in results
        for score in result.semantic_scores.model_dump().values()
        if score is not None
    ]
    def suite_summary(suite: str) -> CategorySummary:
        suite_results = [result for result in results if suite in result.suites]
        passed = sum(result.passed for result in suite_results)
        total = len(suite_results)
        return CategorySummary(total=total, passed=passed, pass_rate=passed / total if total else 0.0)

    hard_safety_failures = sum(
        result.hard_checks.has_unsupported_number
        or result.hard_checks.has_unsupported_entity
        or result.hard_checks.ownership_violation
        for result in results
    )
    return HarnessReport(
        total=total,
        passed=passed,
        pass_rate=passed / total if total else 0.0,
        by_category=by_category,
        p0_violation_counts=dict(sorted(p0.items())),
        generator_status_counts=dict(sorted(status.items())),
        semantic_average=sum(semantic_values) / len(semantic_values) if semantic_values else None,
        current_capability=suite_summary("current_baseline"),
        target_capability=suite_summary("target_capability"),
        fallback_rate=status["fallback"] / total if total else 0.0,
        hard_safety_violation_rate=hard_safety_failures / total if total else 0.0,
        attribution_counts=dict(sorted(attribution_counts.items())),
        failures=failures,
        results=results,
    )

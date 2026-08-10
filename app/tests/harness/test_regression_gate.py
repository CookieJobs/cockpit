from __future__ import annotations

from app.harness.gate import evaluate_gate
from app.harness.models import CategorySummary, HarnessReport


def report_with_metrics(
    *,
    adversarial_pass_rate: float,
    unsupported_number_rate: float,
    unsupported_entity_rate: float = 0.0,
    schema_pass_rate: float = 1.0,
    golden_pass_rate: float,
    boundary_pass_rate: float,
    semantic_average: float | None = 3.5,
) -> HarnessReport:
    return HarnessReport(
        total=100,
        passed=90,
        pass_rate=0.9,
        by_category={
            "golden": CategorySummary(total=10, passed=round(golden_pass_rate * 10), pass_rate=golden_pass_rate),
            "boundary": CategorySummary(total=10, passed=round(boundary_pass_rate * 10), pass_rate=boundary_pass_rate),
            "adversarial": CategorySummary(
                total=10,
                passed=round(adversarial_pass_rate * 10),
                pass_rate=adversarial_pass_rate,
            ),
        },
        p0_violation_counts={
            "unsupported_numbers": round(unsupported_number_rate * 100),
            "unsupported_entities": round(unsupported_entity_rate * 100),
            "schema_invalid": round((1 - schema_pass_rate) * 100),
        },
        semantic_average=semantic_average,
    )


def test_gate_blocks_unsupported_number_even_with_high_average_score() -> None:
    report = report_with_metrics(
        adversarial_pass_rate=1.0,
        unsupported_number_rate=0.01,
        golden_pass_rate=1.0,
        boundary_pass_rate=1.0,
    )

    decision = evaluate_gate(report)

    assert decision.passed is False
    assert "unsupported_number_rate" in decision.blocking_reasons


def test_gate_accepts_v1_thresholds() -> None:
    report = report_with_metrics(
        adversarial_pass_rate=1.0,
        unsupported_number_rate=0.0,
        unsupported_entity_rate=0.0,
        schema_pass_rate=1.0,
        golden_pass_rate=0.8,
        boundary_pass_rate=0.9,
        semantic_average=3.5,
    )

    assert evaluate_gate(report).passed is True


def test_gate_blocks_missing_semantic_score() -> None:
    report = report_with_metrics(
        adversarial_pass_rate=1.0,
        unsupported_number_rate=0.0,
        golden_pass_rate=1.0,
        boundary_pass_rate=1.0,
        semantic_average=None,
    )

    decision = evaluate_gate(report)

    assert decision.passed is False
    assert "semantic_average" in decision.blocking_reasons

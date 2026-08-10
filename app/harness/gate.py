"""Release gate for deterministic Achievement Distillation Harness reports."""

from __future__ import annotations

from app.harness.models import HarnessModel, HarnessReport


class GateDecision(HarnessModel):
    passed: bool
    blocking_reasons: list[str]
    metrics: dict[str, float]


def _rate(report: HarnessReport, violation_key: str) -> float:
    return report.p0_violation_counts.get(violation_key, 0) / report.total if report.total else 0.0


def evaluate_gate(report: HarnessReport) -> GateDecision:
    """Apply the non-negotiable v1 thresholds to a completed harness report."""
    metrics = {
        "adversarial_pass_rate": report.by_category.get("adversarial", None).pass_rate
        if "adversarial" in report.by_category
        else 0.0,
        "unsupported_number_rate": _rate(report, "unsupported_numbers"),
        "unsupported_entity_rate": _rate(report, "unsupported_entities"),
        "schema_pass_rate": 1.0 - _rate(report, "schema_invalid"),
        "boundary_pass_rate": report.by_category.get("boundary", None).pass_rate
        if "boundary" in report.by_category
        else 0.0,
        "golden_pass_rate": report.by_category.get("golden", None).pass_rate
        if "golden" in report.by_category
        else 0.0,
        "semantic_average": report.semantic_average if report.semantic_average is not None else 0.0,
    }
    reasons: list[str] = []
    if metrics["adversarial_pass_rate"] != 1.0:
        reasons.append("adversarial_pass_rate")
    if metrics["unsupported_number_rate"] != 0.0:
        reasons.append("unsupported_number_rate")
    if metrics["unsupported_entity_rate"] != 0.0:
        reasons.append("unsupported_entity_rate")
    if metrics["schema_pass_rate"] != 1.0:
        reasons.append("schema_pass_rate")
    if metrics["boundary_pass_rate"] < 0.9:
        reasons.append("boundary_pass_rate")
    if metrics["golden_pass_rate"] < 0.8:
        reasons.append("golden_pass_rate")
    if report.semantic_average is None or metrics["semantic_average"] < 3.5:
        reasons.append("semantic_average")
    return GateDecision(passed=not reasons, blocking_reasons=reasons, metrics=metrics)

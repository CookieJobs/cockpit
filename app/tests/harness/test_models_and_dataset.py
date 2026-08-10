import json
from pathlib import Path

import pytest
from app.harness.datasets import load_cases
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
    EvaluationResult,
    HardChecks,
    JudgeResult,
    SemanticScores,
)
from pydantic import ValidationError


def test_dataset_has_expected_case_counts() -> None:
    cases = load_cases()
    assert len(cases) == 30
    assert sum(c.category == "golden" for c in cases) == 10
    assert sum(c.category == "boundary" for c in cases) == 12
    assert sum(c.category == "adversarial" for c in cases) == 8


def test_input_requires_title_and_outcome() -> None:
    with pytest.raises(ValidationError):
        AchievementDistillationInput(task_title="", outcome="", language="zh")


def test_input_requires_title_and_outcome_fields() -> None:
    with pytest.raises(ValidationError):
        AchievementDistillationInput(outcome="done", language="zh")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AchievementDistillationInput(task_title="done", language="zh")  # type: ignore[call-arg]


def test_output_and_case_literals_validate() -> None:
    with pytest.raises(ValidationError):
        AchievementDistillationOutput(cv="x", follow_up_questions=[], generator_status="oops")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        AchievementDistillationCase(
            id="x",
            category="invalid",  # type: ignore[arg-type]
            input=AchievementDistillationInput(task_title="t", outcome="o", language="zh"),
            expected={},
            forbidden=[],
            severity="p0",
        )


def test_hard_checks_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        HardChecks(
            schema_valid=True,
            length_valid=True,
            has_strong_action=True,
            has_unsupported_number=False,
            has_unsupported_entity=False,
            likely_duplicate_outcome=False,
            likely_overclaim=False,
            unsupported_numbers=[],
            unsupported_entities=[],
            ownership_violation=False,
            unexpected_field=True,  # type: ignore[call-arg]
        )


def test_evaluation_result_requires_explicit_nested_contracts() -> None:
    result = EvaluationResult(
        case_id="case_1",
        category="golden",
        output=AchievementDistillationOutput(
            cv="改进搜索体验",
            follow_up_questions=[],
            generator_status="polished",
        ),
        hard_checks=HardChecks(
            schema_valid=True,
            length_valid=True,
            has_strong_action=True,
            has_unsupported_number=False,
            has_unsupported_entity=False,
            likely_duplicate_outcome=False,
            likely_overclaim=False,
            unsupported_numbers=[],
            unsupported_entities=[],
            ownership_violation=False,
        ),
        semantic_scores=SemanticScores(
            impact_clarity=4,
            specificity=4,
            authenticity=4,
            resume_usefulness=4,
            follow_up_usefulness=4,
        ),
        judge=JudgeResult(score=4, violations=[], suggestions=[]),
        passed=True,
    )
    assert result.output.cv == "改进搜索体验"
    assert result.hard_checks.schema_valid is True


def test_case_contains_expected_and_forbidden_behavior() -> None:
    case = next(c for c in load_cases() if c.id == "boundary_participation")
    assert case.expected["action"] == "参与"
    assert "主导" in case.forbidden


def test_dataset_separates_current_and_target_suites() -> None:
    cases = load_cases()
    current = [case for case in cases if "current_baseline" in case.suites]
    target = [case for case in cases if "target_capability" in case.suites]

    assert len(current) > 0
    assert len(target) > len(current)
    assert all("target_capability" in case.suites for case in cases if case.category == "adversarial")


def test_loader_accepts_explicit_path(tmp_path: Path) -> None:
    dataset = [
        {
            "id": "custom_case",
            "category": "golden",
            "input": {
                "task_title": "整理复盘",
                "task_description": None,
                "project_name": None,
                "project_goal": None,
                "outcome": "完成了复盘整理。",
                "reflection": None,
                "language": "zh",
            },
            "expected": {"action": "提炼"},
            "forbidden": [],
            "severity": "p1",
        }
    ]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    cases = load_cases(path)
    assert len(cases) == 1
    assert cases[0].id == "custom_case"


def test_loader_reports_offending_case_id(tmp_path: Path) -> None:
    dataset = [
        {
            "id": "broken_case",
            "category": "golden",
            "input": {
                "task_title": "整理复盘",
                "task_description": None,
                "project_name": None,
                "project_goal": None,
                "reflection": None,
                "language": "zh",
            },
            "expected": {"action": "提炼"},
            "forbidden": [],
            "severity": "p1",
        }
    ]
    path = tmp_path / "bad_dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="broken_case"):
        load_cases(path)

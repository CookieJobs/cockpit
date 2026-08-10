"""Pydantic models for the achievement distillation harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HarnessModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
        extra="forbid",
    )


class AchievementDistillationInput(HarnessModel):
    task_title: str = Field(..., min_length=1, max_length=500)
    task_description: str | None = Field(default=None, min_length=1, max_length=5000)
    project_name: str | None = Field(default=None, min_length=1, max_length=200)
    project_goal: str | None = Field(default=None, min_length=1, max_length=2000)
    outcome: str = Field(..., min_length=1, max_length=5000)
    reflection: str | None = Field(default=None, min_length=1, max_length=5000)
    language: str = Field(..., min_length=1, max_length=20)


class AchievementDistillationOutput(HarnessModel):
    cv: str = Field(..., min_length=1, max_length=5000)
    follow_up_questions: list[str] = Field(default_factory=list)
    generator_status: Literal["polished", "fallback", "parse_failed"]


class SemanticScores(HarnessModel):
    impact_clarity: float | None = Field(default=None, ge=1, le=5)
    specificity: float | None = Field(default=None, ge=1, le=5)
    authenticity: float | None = Field(default=None, ge=1, le=5)
    resume_usefulness: float | None = Field(default=None, ge=1, le=5)
    follow_up_usefulness: float | None = Field(default=None, ge=1, le=5)


class JudgeResult(HarnessModel):
    score: float | None = Field(default=None, ge=1, le=5)
    violations: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class HardChecks(HarnessModel):
    schema_valid: bool
    length_valid: bool
    follow_up_count_valid: bool = True
    has_strong_action: bool
    has_unsupported_number: bool
    has_unsupported_entity: bool
    likely_duplicate_outcome: bool
    likely_overclaim: bool
    generator_is_fallback: bool = False
    generator_is_parse_failed: bool = False
    unsupported_numbers: list[str] = Field(default_factory=list)
    unsupported_entities: list[str] = Field(default_factory=list)
    ownership_violation: bool


class EvaluationResult(HarnessModel):
    case_id: str = Field(..., min_length=1)
    category: Literal["golden", "boundary", "adversarial"]
    output: AchievementDistillationOutput
    hard_checks: HardChecks
    semantic_scores: SemanticScores
    judge: JudgeResult
    passed: bool


class CategorySummary(HarnessModel):
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class FailureSummary(HarnessModel):
    case_id: str
    category: Literal["golden", "boundary", "adversarial"]
    violations: list[str] = Field(default_factory=list)


class HarnessMetadata(HarnessModel):
    model_version: str = "unknown"
    prompt_version: str = "polish_cv_v0.3.4"
    dataset_version: str = "achievement_distillation_v1"
    harness_version: str = "v1"


class HarnessReport(HarnessModel):
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    by_category: dict[str, CategorySummary] = Field(default_factory=dict)
    p0_violation_counts: dict[str, int] = Field(default_factory=dict)
    generator_status_counts: dict[str, int] = Field(default_factory=dict)
    semantic_average: float | None = Field(default=None, ge=1.0, le=5.0)
    metadata: HarnessMetadata = Field(default_factory=HarnessMetadata)
    failures: list[FailureSummary] = Field(default_factory=list)
    results: list[EvaluationResult] = Field(default_factory=list)


class AchievementDistillationCase(HarnessModel):
    id: str = Field(..., min_length=1)
    category: Literal["golden", "boundary", "adversarial"]
    input: AchievementDistillationInput
    expected: dict[str, Any] = Field(default_factory=dict)
    forbidden: list[str] = Field(default_factory=list)
    severity: Literal["p0", "p1"]


def dataset_path() -> Path:
    return Path(__file__).resolve().parent / "datasets" / "achievement_distillation_v1.json"

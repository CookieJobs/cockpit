"""Provider-neutral LLM Judge contract for semantic harness scoring."""

from __future__ import annotations

import json
from typing import Protocol

from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationOutput,
    JudgeResult,
    SemanticScores,
)

JUDGE_PROMPT_VERSION = "achievement_distillation_judge_v1"


class JudgeAdapter(Protocol):
    async def judge(self, case: AchievementDistillationCase, output: AchievementDistillationOutput) -> str: ...


def parse_judge_output(raw: str) -> tuple[JudgeResult, SemanticScores]:
    """Accept only the documented JSON shape; callers can record failures safely."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("judge output must be a JSON object")
    scores = SemanticScores.model_validate(payload.get("semantic_scores", {}))
    return JudgeResult(
        score=payload.get("score"),
        violations=payload.get("violations", []),
        suggestions=payload.get("suggestions", []),
    ), scores


class FakeJudge:
    """Deterministic judge used only by unit tests and fixture runs."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    async def judge(self, case: AchievementDistillationCase, output: AchievementDistillationOutput) -> str:
        return self.responses[case.id]

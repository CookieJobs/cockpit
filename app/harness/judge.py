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

CURRENT_SEMANTIC_JUDGE_SYSTEM = """你是 Cockpit 成就蒸馏评测的独立评分器。
仅评价给定用户事实、生成 CV 和追问；不要生成或改写 CV。

按 1-5 分评价：
- authenticity：是否超出用户事实；
- impact_clarity：是否表达具体价值而非复读动作；
- resume_usefulness：是否适合长期职业资产；
- follow_up_usefulness：追问是否有信息增益、无重复、无凭空假设。
  若用户事实已足够具体，空数组表示无需追问，应给高分；只在信息缺口明显却没有追问时扣分。

不要判定数字、实体、角色归属的字面可溯源性，它们由 deterministic evaluator 负责。
只输出 JSON：
{"scores":{"authenticity":1,"impact_clarity":1,"resume_usefulness":1,"follow_up_usefulness":1},"violations":[],"reason":"","suggestions":[]}"""


class JudgeAdapter(Protocol):
    async def judge(self, case: AchievementDistillationCase, output: AchievementDistillationOutput) -> str: ...


class CurrentLLMJudge:
    """Minimal offline judge using an explicitly supplied LLM client.

    It is never imported by the production distillation path. Callers choose it
    explicitly for a live harness run, so model cost and judge provenance stay
    visible in the report command.
    """

    def __init__(self, client) -> None:
        self._client = client

    async def judge(self, case: AchievementDistillationCase, output: AchievementDistillationOutput) -> str:
        payload = {
            "用户事实": {
                "task_title": case.input.task_title,
                "task_description": case.input.task_description,
                "project_name": case.input.project_name,
                "project_goal": case.input.project_goal,
                "outcome": case.input.outcome,
                "reflection": case.input.reflection,
            },
            "生成 CV": output.cv,
            "追问": output.follow_up_questions,
            "generator_status": output.generator_status,
        }
        response = await self._client.chat(
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            system=CURRENT_SEMANTIC_JUDGE_SYSTEM,
            tools=None,
        )
        if response.stop_reason == "error" or not response.text:
            raise ValueError(response.error or "empty judge response")
        return response.text


def build_current_judge(client) -> CurrentLLMJudge | None:
    """Keep an unavailable optional judge from breaking a live baseline run."""
    return CurrentLLMJudge(client) if client is not None else None


def parse_judge_output(raw: str) -> tuple[JudgeResult, SemanticScores]:
    """Accept only the documented JSON shape; callers can record failures safely."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("judge output must be a JSON object")
    # `scores` is the v1 external contract; keep `semantic_scores` readable
    # for already-recorded fixture outputs.
    scores = SemanticScores.model_validate(payload.get("scores", payload.get("semantic_scores", {})))
    return JudgeResult(
        score=payload.get("score"),
        violations=payload.get("violations", []),
        reason=payload.get("reason", ""),
        suggestions=payload.get("suggestions", []),
    ), scores


class FakeJudge:
    """Deterministic judge used only by unit tests and fixture runs."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    async def judge(self, case: AchievementDistillationCase, output: AchievementDistillationOutput) -> str:
        return self.responses[case.id]

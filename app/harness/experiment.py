"""Offline prompt variants for capability experiments; never used by production routes."""

from __future__ import annotations

from app.api.llm import (
    POLISH_CV_SYSTEM,
    PolishCvRequest,
    PolishCvResponse,
    _fallback_cv,
    _has_p0_runtime_violation,
    _parse_llm_json_output,
    _runtime_guardrail_results,
)
from app.harness.models import AchievementDistillationInput, AchievementDistillationOutput
from app.llm.base import text_message

GROUNDING_EXPERIMENT_SUFFIX = """

【实验性事实约束 — 仅离线评测，不改变生产行为】
- 不得把参与、协助、配合、跟进升级为主导、独立、负责或 owner，除非用户 outcome 明确如此表述。
- CV 中的每一个数字必须以相同形式出现在用户提供的事实中；不得计算或新造百分比、倍数、人数、规模。
- 不要把“从0到1”、业务指标明显提升、显著减少等未给出的影响写入 CV。
- 用户已提供具体结果时，follow_up_questions 必须为空；仅在事实确有缺口时追问。
"""


class GroundedPromptAdapter:
    """Candidate implementation for a prompt-only grounding experiment."""

    def __init__(self, client) -> None:
        self._client = client

    async def generate(self, input: AchievementDistillationInput) -> AchievementDistillationOutput:
        response = await self._client.chat(
            messages=[text_message("user", f"任务标题：{input.task_title}\n结果描述：{input.outcome}")],
            system=POLISH_CV_SYSTEM + GROUNDING_EXPERIMENT_SUFFIX,
            tools=None,
        )
        if response.stop_reason == "error" or not response.text:
            return AchievementDistillationOutput(cv="生成失败", generator_status="parse_failed")
        cv, questions = _parse_llm_json_output(response.text)
        if cv is None:
            return AchievementDistillationOutput(cv="生成失败", generator_status="parse_failed")
        output = AchievementDistillationOutput(
            cv=cv,
            follow_up_questions=questions,
            generator_status="polished",
        )
        request = PolishCvRequest(task_title=input.task_title, outcome=input.outcome)
        response_model = PolishCvResponse(cv=cv, polished=True, follow_up_questions=questions)
        if _has_p0_runtime_violation(_runtime_guardrail_results(request, response_model)):
            return AchievementDistillationOutput(
                cv=_fallback_cv(input.task_title),
                follow_up_questions=questions or ["这项工作的实际影响、范围或量化结果是什么？"],
                generator_status="fallback",
            )
        return output

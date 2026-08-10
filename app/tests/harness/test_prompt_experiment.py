from __future__ import annotations

import pytest
from app.harness.experiment import GroundedPromptAdapter
from app.harness.models import AchievementDistillationInput
from app.llm.base import LLMResponse


@pytest.mark.asyncio
async def test_grounded_prompt_adapter_adds_provenance_constraints() -> None:
    class Client:
        async def chat(self, messages, system, tools=None):
            assert tools is None
            assert "不得把参与、协助、配合、跟进升级为主导" in system
            assert "不得计算或新造" in system
            assert "任务标题：登录优化" in messages[0]["content"]
            return LLMResponse(text='{"cv":"优化登录流程，耗时从2秒降至0.5秒","follow_up_questions":[]}')

    output = await GroundedPromptAdapter(Client()).generate(
        AchievementDistillationInput(task_title="登录优化", outcome="耗时从2秒降至0.5秒", language="zh")
    )

    assert output.generator_status == "polished"
    assert output.cv == "优化登录流程，耗时从2秒降至0.5秒"


@pytest.mark.asyncio
async def test_grounded_prompt_adapter_marks_unparseable_response() -> None:
    class Client:
        async def chat(self, messages, system, tools=None):
            return LLMResponse(text="not json")

    output = await GroundedPromptAdapter(Client()).generate(
        AchievementDistillationInput(task_title="登录优化", outcome="完成优化", language="zh")
    )

    assert output.generator_status == "parse_failed"


@pytest.mark.asyncio
async def test_grounded_prompt_adapter_preserves_runtime_ownership_guardrail() -> None:
    class Client:
        async def chat(self, messages, system, tools=None):
            return LLMResponse(text='{"cv":"主导登录优化","follow_up_questions":[]}')

    output = await GroundedPromptAdapter(Client()).generate(
        AchievementDistillationInput(task_title="登录优化", outcome="参与登录优化", language="zh")
    )

    assert output.generator_status == "fallback"
    assert output.cv == "完成「登录优化」"

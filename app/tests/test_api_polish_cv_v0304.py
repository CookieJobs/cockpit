"""polish_cv prompt 质量升级测试 (v0.3.4 立, 2026-08-02)。

锁住 v0.3.4 升级的 3 个关键约束:
1. POLISH_CV_SYSTEM 必含强动词清单 (v0.3.4 立)
2. POLISH_CV_SYSTEM 必含弱动词禁止清单 (v0.3.4 立)
3. POLISH_CV_SYSTEM 必含 few-shot 强/弱对比 (v0.3.4 立)
4. POLISH_CV_SYSTEM 必含量化硬指标要求 (v0.3.4 立)
5. 弱 cv LLM 输出应触发追问 (v0.3.4 强化: 没量化 = 必追问)

为什么这个测试: prompt 是 LLM 行为的唯一约束, prompt 退化 = cv 质量退化.
即便 LLM 升级 / 后端换, prompt 不退化就能锁住 cv 质量.
"""
import re
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.llm import POLISH_CV_SYSTEM
from app.llm.base import LLMResponse
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


# ========================================================================
# 1. Prompt 静态约束 — 锁住 v0.3.4 升级的关键词, 防 prompt 退化
# ========================================================================

def test_polish_prompt_contains_strong_verbs():
    """v0.3.4: prompt 必含强动词清单, 至少 5 个强动作动词."""
    strong_verbs = ["构建", "设计", "重构", "推动", "主导", "优化", "修复", "落地", "引入", "沉淀"]
    found = [v for v in strong_verbs if v in POLISH_CV_SYSTEM]
    assert len(found) >= 5, (
        f"v0.3.4 prompt 应至少含 5 个强动作动词, 只找到 {len(found)}: {found}\n"
        f"完整 prompt:\n{POLISH_CV_SYSTEM}"
    )


def test_polish_prompt_prevents_weak_ownership_from_being_upgraded():
    """事实优先：弱 ownership 表述不能被 prompt 鼓励升级。"""
    weak_verbs = ["负责", "参与", "协助", "处理"]
    # 至少含 3 个, 且明确说"严禁"或类似禁止语义
    prohibit_phrase = "严禁"
    assert prohibit_phrase in POLISH_CV_SYSTEM, (
        f"prompt 应明确含「{prohibit_phrase}」的事实性边界"
    )
    found = [v for v in weak_verbs if v in POLISH_CV_SYSTEM]
    assert len(found) >= 3, (
        f"prompt 应至少覆盖 3 个 ownership 边界词, 只找到 {len(found)}: {found}\n"
        f"完整 prompt:\n{POLISH_CV_SYSTEM}"
    )


def test_polish_prompt_contains_quantification_requirement():
    """量化应被鼓励，但只能复用用户事实。"""
    has_quantify = "量化" in POLISH_CV_SYSTEM
    has_hard_marker = any(
        marker in POLISH_CV_SYSTEM
        for marker in ["硬指标", "必追问", "必须", "【量化是硬指标】"]
    )
    assert has_quantify, "prompt 应含「量化」关键词"
    assert has_hard_marker, "prompt 应说明何时需要追问量化事实"


def test_polish_prompt_prioritizes_grounded_facts_over_strength():
    """Harness experiment: stronger wording may never invent ownership or metrics."""
    assert "不得把参与、协助、配合、跟进升级为主导" in POLISH_CV_SYSTEM
    assert "不得计算或新造" in POLISH_CV_SYSTEM
    assert "用户已提供具体结果时，follow_up_questions 必须为空" in POLISH_CV_SYSTEM


def test_polish_prompt_contains_few_shot_examples():
    """v0.3.4: prompt 必含至少 2 对强/弱对比示例."""
    # 找 ❌ 和 ✅ 标记 (强/弱对比)
    has_weak_marker = "❌" in POLISH_CV_SYSTEM
    has_strong_marker = "✅" in POLISH_CV_SYSTEM
    assert has_weak_marker, "v0.3.4 prompt 应含 ❌ 弱示例"
    assert has_strong_marker, "v0.3.4 prompt 应含 ✅ 强示例"
    # 至少 2 对
    weak_count = POLISH_CV_SYSTEM.count("❌")
    strong_count = POLISH_CV_SYSTEM.count("✅")
    assert weak_count >= 2 and strong_count >= 2, (
        f"v0.3.4 prompt 应至少 2 对对比示例, 实际 ❌={weak_count} ✅={strong_count}"
    )


def test_polish_prompt_follow_up_question_strengthening():
    """v0.3.4: 追问机制必须强化 — 优先级: 影响范围 > 量化收益 > 团队规模 > 时间成本."""
    # 至少含 "影响" "量化" 这两个优先级关键词
    assert "影响" in POLISH_CV_SYSTEM, "v0.3.4 追问优先级应含「影响」"
    assert "量化" in POLISH_CV_SYSTEM, "v0.3.4 追问优先级应含「量化」"
    # 追问机制段应存在
    assert "追问" in POLISH_CV_SYSTEM, "v0.3.4 prompt 应保留追问机制"


def test_polish_prompt_preserves_json_output_format():
    """v0.3.4: prompt 必须保留 JSON 输出格式约束 (不要退化)."""
    assert "{" in POLISH_CV_SYSTEM and "}" in POLISH_CV_SYSTEM, (
        "prompt 应含 JSON 格式示例 { ... }"
    )
    assert "cv" in POLISH_CV_SYSTEM and "follow_up_questions" in POLISH_CV_SYSTEM, (
        "prompt 应含 JSON 字段名 cv 和 follow_up_questions"
    )
    # CoT 禁止
    assert "<think>" in POLISH_CV_SYSTEM, "prompt 应含 CoT 禁止规则"


# ========================================================================
# 2. 端到端: LLM 返"弱 cv" (无量化) → 追问必返
# ========================================================================

@pytest.mark.asyncio
async def test_weak_cv_triggers_followup(client: TestClient):
    """v0.3.4 强化: 弱 cv (无量化) → follow_up_questions 必有追问."""
    mock_client = AsyncMock()
    # LLM 返的弱 cv + 强追问 (v0.3.4 强化语义)
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "完成「修 bug」", "follow_up_questions": ["这个 bug 影响多少用户?", "修复后 DAU/留存变化了多少?"]}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "修登录 bug", "outcome": "修好了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # v0.3.4 强化: 弱 cv 必追问
    assert len(body["follow_up_questions"]) > 0, (
        "v0.3.4 强化: 弱 cv 必触发追问, 实际返空数组 (LLM 没遵守 prompt)"
    )
    # 追问应该问"量化"
    assert any("多少" in q or "几" in q or "多长" in q for q in body["follow_up_questions"]), (
        f"v0.3.4 追问应是量化型, 实际: {body['follow_up_questions']}"
    )


@pytest.mark.asyncio
async def test_strong_cv_skips_followup(client: TestClient):
    """v0.3.4: 强 cv (含量化) → follow_up_questions 必空."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "定位并修复登录鉴权高优先级 bug, 消除用户阻塞, DAU 提升 5%", "follow_up_questions": []}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={
                "task_title": "登录 bug",
                "outcome": "修复登录 bug, DAU 提升 5%, 影响 10 万日活",
            },
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 强 cv (含量化) → 不追问
    assert body["follow_up_questions"] == [], (
        f"强 cv 不应追问, 实际: {body['follow_up_questions']}"
    )
    # cv 必含量化
    assert re.search(r"\d+%|\d+万|\d+倍", body["cv"]), (
        f"v0.3.4 强 cv 必含量化, 实际: {body['cv']}"
    )


@pytest.mark.asyncio
async def test_prompt_sent_to_llm_contains_v0304_constraints(client: TestClient):
    """v0.3.4 验证: 实际发给 LLM 的 system prompt 必含 v0.3.4 新约束 (不只是源码里)."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="end_turn", text="测试")
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        client.post(
            "/api/llm/polish_cv",
            json={"task_title": "测试", "outcome": "测试"},
        )
    # 拿到实际发的 system prompt
    call_kwargs = mock_client.chat.call_args.kwargs
    actual_system = call_kwargs.get("system", "")
    # v0.3.4 必含的关键约束
    assert "强动作动词" in actual_system or any(
        v in actual_system for v in ["构建", "设计", "重构", "推动", "主导"]
    ), f"实际发的 system prompt 没含强动词约束: {actual_system[:200]}"
    assert "❌" in actual_system, "实际发的 system prompt 没含 few-shot 对比示例"

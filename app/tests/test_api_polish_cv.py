"""polish_cv 端点测试 (2026-07-28 立)。

设计目标:
- LLM 路径: 调 LLM 把 outcome 润色成 CV 风格
- Fallback 路径: LLM 不可用 / 调用失败时返回 `完成「title」`, 走 polished=False
- 关键: LLM 失败不能抛 500 (避免润色失败把整个完成流程堵死)

测 3 件事:
1. LLM 不可用 → 静默 fallback
2. LLM 抛异常 → 静默 fallback
3. LLM 正常 → 返回润色结果 + polished=True
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.llm.base import LLMResponse
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_polish_cv_no_llm_client_returns_fallback(client: TestClient):
    """无 LLM client (无 API key / 健康检查失败) → 静默返回兜底, 不抛 500。"""
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=None)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "修复登录 bug", "outcome": "用户反馈登录 bug 已修复, DAU 提升 5%"},
        )
    assert res.status_code == 200, f"应该静默 fallback, 不抛 500: {res.text}"
    body = res.json()
    assert body["polished"] is False
    assert body["cv"] == "完成「修复登录 bug」"


@pytest.mark.asyncio
async def test_polish_cv_llm_exception_returns_fallback(client: TestClient):
    """LLM 调用抛异常 → 静默 fallback。"""
    mock_client = AsyncMock()
    mock_client.chat.side_effect = RuntimeError("network down")
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "PPT 演讲", "outcome": "完成了述职 PPT"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is False
    assert body["cv"] == "完成「PPT 演讲」"


@pytest.mark.asyncio
async def test_polish_cv_llm_error_response_returns_fallback(client: TestClient):
    """LLM 返回 stop_reason=error / text 为空 → fallback。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="error", error="rate limit", text="")
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "代码重构", "outcome": "重构了用户模块"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is False
    assert body["cv"] == "完成「代码重构」"


@pytest.mark.asyncio
async def test_polish_cv_llm_success_returns_polished(client: TestClient):
    """LLM 正常返回 → 润色后的 CV + polished=True。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text="定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%",
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录 bug", "outcome": "用户反馈登录 bug 已修复, DAU 提升 5%"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert "修复" in body["cv"]
    assert "DAU" in body["cv"]


@pytest.mark.asyncio
async def test_polish_cv_strips_quotes(client: TestClient):
    """LLM 输出带引号 (claude 习惯) → 后端要清理。"""
    mock_client = AsyncMock()
    cv_text = "定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%"
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text=f'"{cv_text}"',  # 带双引号
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录 bug", "outcome": "用户反馈登录 bug 已修复"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 不应该有引号
    assert not body["cv"].startswith('"') and not body["cv"].endswith('"')
    assert body["cv"] == cv_text


@pytest.mark.asyncio
async def test_polish_cv_truncates_long_output(client: TestClient):
    """LLM 输出超 200 字 → 截断到 200 + "..."。"""
    mock_client = AsyncMock()
    # 故意造超 250 字的输出 (用 Python 拼接保证长度)
    long_cv = (
        "完成登录鉴权模块重构，引入 token rotation 机制，覆盖所有 12 个 API 端点，"
        "单元测试覆盖率从 62% 提升到 91%，线上鉴权失败率下降 73%，"
        "并形成 3 篇内部 wiki 文档供后续接入参考，本季度还协助 2 个新团队完成接入，"
        "节省后续人力约 30 人天，相关经验总结为最佳实践供全公司参考，"
        "并在季度复盘会议分享，获得优秀案例奖，纳入公司年度技术分享名单，"
        "跨 3 个 BU 推广，影响范围持续扩大"
    )
    assert len(long_cv) > 200, f"测试数据长度 {len(long_cv)} 必须 > 200 才能触发截断"
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="end_turn", text=long_cv)
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "鉴权重构", "outcome": "鉴权重构"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 截断后长度应该 <= 200 + len("...") = 203
    assert len(body["cv"]) <= 203, f"截断失败, 长度 {len(body['cv'])}"
    # 应该以 "..." 结尾
    assert body["cv"].endswith("...")


@pytest.mark.asyncio
async def test_polish_cv_empty_outcome_after_strip_returns_fallback(client: TestClient):
    """LLM 返回纯空白 (罕见但要兜底) → fallback。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="end_turn", text="   \n  ")
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "X", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is False
    assert body["cv"] == "完成「X」"


@pytest.mark.asyncio
async def test_polish_cv_missing_outcome_returns_422(client: TestClient):
    """outcome 必填, 缺了返 422 (Pydantic 校验)。"""
    res = client.post(
        "/api/llm/polish_cv",
        json={"task_title": "X"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_polish_cv_empty_outcome_string_returns_422(client: TestClient):
    """outcome 空字符串也返 422 (min_length=1)。"""
    res = client.post(
        "/api/llm/polish_cv",
        json={"task_title": "X", "outcome": ""},
    )
    assert res.status_code == 422


# ===== follow_up_questions (2026-07-30 立, lesson #15) =====
#
# 新设计: LLM 必要时返 JSON {cv, follow_up_questions}
# - 信息够具体: questions=[]
# - 信息太抽象: questions=[1-2 个针对任务标题的追问]
# - 鲁棒性: JSON 解析失败走老路径 (整段当 cv + questions=[])


@pytest.mark.asyncio
async def test_polish_cv_llm_returns_json_with_questions(client: TestClient):
    """LLM 严格返 JSON 含 follow_up_questions → response 透传 questions 字段。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "输出 App 改版 PRD，覆盖 18 个核心场景", "follow_up_questions": ["这份是给谁看的？", "评审结果怎么样？"]}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "完成 PRD", "outcome": "完成 PRD"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert "PRD" in body["cv"]
    assert body["follow_up_questions"] == ["这份是给谁看的？", "评审结果怎么样？"]


@pytest.mark.asyncio
async def test_polish_cv_llm_json_with_no_questions_when_info_enough(client: TestClient):
    """LLM 返 JSON 但 follow_up_questions=[] (信息够了) → response questions=[]。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "定位并修复高优先级登录鉴权 bug，影响 5% DAU 用户，2 小时内解决", "follow_up_questions": []}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "修 bug", "outcome": "修了登录 bug，影响 5% DAU，2 小时内解决"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_llm_json_codeblock_wrapper_parsed(client: TestClient):
    """LLM 返 ```json ... ``` markdown 代码块包装 → 鲁棒解析成功。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='```json\n{"cv": "输出 PRD 覆盖 18 个核心场景", "follow_up_questions": ["给谁看？"]}\n```',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "完成 PRD", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert "PRD" in body["cv"]
    assert body["follow_up_questions"] == ["给谁看？"]


@pytest.mark.asyncio
async def test_polish_cv_llm_plain_text_falls_back_to_legacy_path(client: TestClient):
    """LLM 返纯文本 (老格式 / 不严格 JSON) → 整段当 cv + questions=[] 老路径。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text="定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%",  # 没 JSON 包装
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录 bug", "outcome": "修了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 老路径: 整段当 cv
    assert "登录" in body["cv"]
    # questions 必为空 (老格式不返 questions, 不能编)
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_llm_json_with_empty_cv_falls_back_to_legacy(client: TestClient):
    """LLM 返 JSON 但 cv 字段为空 → 走老路径 (整段当 cv), questions=[]。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "", "follow_up_questions": ["问1"]}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "X", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    # cv 解析失败 (空字符串) → 走老路径: 整段当 cv, polished=True
    assert body["polished"] is True
    # 老路径不返 questions
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_no_llm_returns_empty_questions(client: TestClient):
    """无 LLM (无 API key) → fallback + questions 必为空数组。"""
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=None)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "完成 PRD", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is False
    assert body["cv"] == "完成「完成 PRD」"
    # fallback 路径: 必返空数组, 关键不变量 (前端 followUpQuestions.length > 0 判断依赖)
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_llm_exception_returns_empty_questions(client: TestClient):
    """LLM 抛异常 → fallback + questions=[] (不抛 500, 不污染主流程)。"""
    mock_client = AsyncMock()
    mock_client.chat.side_effect = RuntimeError("network down")
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "X", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is False
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_llm_response_always_has_follow_up_questions_field(client: TestClient):
    """response schema 不变量: 无论什么路径 (fallback / 异常 / LLM 正常), follow_up_questions 字段必存在。"""
    # 路径 1: fallback
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=None)):
        res = client.post("/api/llm/polish_cv", json={"task_title": "X", "outcome": "Y"})
        assert "follow_up_questions" in res.json()
        assert isinstance(res.json()["follow_up_questions"], list)

    # 路径 2: LLM 异常
    mock_client = AsyncMock()
    mock_client.chat.side_effect = RuntimeError("err")
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post("/api/llm/polish_cv", json={"task_title": "X", "outcome": "Y"})
        assert "follow_up_questions" in res.json()
        assert isinstance(res.json()["follow_up_questions"], list)

    # 路径 3: LLM 正常
    mock_client2 = AsyncMock()
    mock_client2.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="end_turn", text='{"cv": "X", "follow_up_questions": []}')
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client2)):
        res = client.post("/api/llm/polish_cv", json={"task_title": "X", "outcome": "Y"})
        assert "follow_up_questions" in res.json()
        assert isinstance(res.json()["follow_up_questions"], list)


@pytest.mark.asyncio
async def test_polish_cv_questions_max_length_capped_at_3(client: TestClient):
    """follow_up_questions 超过 3 个时, 截断到 3 (schema 限制 + 防止 LLM 啰嗦)。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text='{"cv": "X", "follow_up_questions": ["q1", "q2", "q3", "q4", "q5"]}',
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post("/api/llm/polish_cv", json={"task_title": "X", "outcome": "Y"})
    assert res.status_code == 200
    body = res.json()
    # max_length=3 截断
    assert len(body["follow_up_questions"]) <= 3


# ===== 2026-07-30 lesson #16 衍生: M3 / DeepSeek R1 / reasoning model 适配 =====
#
# 用户实测 MiniMax-M3 LLM 返 "<think>...</think>" CoT 前缀, 我们的 _parse_llm_json_output
# 没处理这种情况, 导致 follow_up_questions 永远空数组, 追问卡片前端不显示.
# 修复: 加 <think> 剥离 + 平衡大括号 JSON 块提取.


@pytest.mark.asyncio
async def test_polish_cv_strips_think_block_and_parses_json(client: TestClient):
    """LLM 返 <think>...</think> CoT + 紧跟 JSON → 剥 CoT 后解析成功, follow_up_questions 透传."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text=(
                "<think>The user gave a very abstract outcome '做完了'. "
                "I should ask 2 follow-up questions specific to '完成 PRD' task type.</think>"
                '{"cv": "完成「完成 PRD」", "follow_up_questions": ["这份是给谁看的？", "评审结果怎么样？"]}'
            ),
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "完成 PRD", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 关键: cv 不应该含 <think>, 应该是解析后的 JSON cv
    assert "<think>" not in body["cv"]
    assert body["cv"] == "完成「完成 PRD」"
    # 关键: 追问真的传出来了 (这是用户看不到效果的根因)
    assert body["follow_up_questions"] == ["这份是给谁看的？", "评审结果怎么样？"]


@pytest.mark.asyncio
async def test_polish_cv_think_block_with_natural_language_prefix(client: TestClient):
    """LLM 返: 自然语言 + <think> + JSON → 全部清洗后解析成功."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text=(
                "好的, 让我分析一下这个任务。\n"
                "<think>The outcome is abstract, need follow-ups.</think>\n"
                '这是我的润色结果: {"cv": "修复登录 bug 影响 5% DAU", "follow_up_questions": []}'
            ),
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "修 bug", "outcome": "修了登录 bug, 影响 5% DAU"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert "<think>" not in body["cv"]
    assert "好的" not in body["cv"]
    assert "润色结果" not in body["cv"]
    assert body["cv"] == "修复登录 bug 影响 5% DAU"
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_realistic_m3_response_with_think_block(client: TestClient):
    """模拟用户真实场景: MiniMax-M3 实际会返的格式."""
    mock_client = AsyncMock()
    # 这是用户实际从后端 curl 拿到的格式 (复刻)
    realistic_text = (
        "<think>The user provided a task title \"完成 PRD\" and result description "
        "\"做完了\". This is clearly too abstract - just \"做完了\" (done) doesn't tell "
        "me anything about who it was for, what impact it had. I need to ask follow-up "
        "questions. Let me also provide a fallback CV.</think>"
        '{"cv": "完成「完成 PRD」", "follow_up_questions": ["这份 PRD 是给谁看的？", "评审结果怎么样？"]}'
    )
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(stop_reason="end_turn", text=realistic_text)
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "完成 PRD", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    # 端到端验证: 这是前端能看到的效果
    assert "<think>" not in body["cv"]
    assert len(body["follow_up_questions"]) > 0, (
        "用户原话: '看不出效果来' — 修复后追问应该真的传出来, "
        "前端 followUpQuestions.length > 0 应该渲染追问卡片"
    )


@pytest.mark.asyncio
async def test_polish_cv_natural_language_only_no_json_legacy_path(client: TestClient):
    """LLM 完全不返 JSON, 只返自然语言 → 走老路径 (整段当 cv + questions=[])."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text="定位并修复高优先级登录鉴权 bug, 消除用户阻塞, DAU 提升 5%",
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "登录 bug", "outcome": "修了"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["polished"] is True
    assert "登录" in body["cv"]
    # 老路径不返 questions
    assert body["follow_up_questions"] == []


@pytest.mark.asyncio
async def test_polish_cv_think_block_with_no_json_falls_back_to_legacy(client: TestClient):
    """LLM 只返 <think> (没配 JSON) → 剥 <think> 后空, 走老路径, 但要返回纯文本兜底."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value=LLMResponse(
            stop_reason="end_turn",
            text=(
                "<think>The user wants me to polish a CV. "
                "I should focus on the action verb and quantified impact. "
                "Let me write something good.</think>"
            ),
        )
    )
    with patch("app.api.llm.get_verified_client", AsyncMock(return_value=mock_client)):
        res = client.post(
            "/api/llm/polish_cv",
            json={"task_title": "X", "outcome": "做完了"},
        )
    assert res.status_code == 200
    body = res.json()
    # 剥完 <think> 啥都没了, cv 解析失败 → 走老路径 (整段空当 cv, strip 后空)
    # 但要 polished=False (因为没有有效 cv)
    # 实际行为: 整段 strip 后空, 走 fallback
    assert body["cv"] == "完成「X」"
    assert body["polished"] is False
    assert body["follow_up_questions"] == []

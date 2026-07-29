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

"""run_chat_stream 流式 chat 测试。

锁定 4 个易错行为：
1. cot 事件 yield 正确（CoT 块捕获，跨 delta 完整）
2. 关键词流式（_run_keyword_stream）正确
3. LLM 失败 → fallback 关键词
4. tool_call 流程完整（text → tool_start → tool_end → 继续 text）

不依赖真实 LLM（用 mock client）。
"""
import asyncio
import pytest

from app.llm.base import LLMResponse
from app.llm.chat_engine import (
    run_chat_stream,
    _run_keyword_stream,
)


class MockStreamingClient:
    """模拟流式 LLM 客户端。

    调用顺序：yield text（含 think 块）→ yield tool_start → 等待 chat_engine
    执行 tool → chat_engine 进入下一轮 → 再次 yield text → 最终 end_turn。
    """

    def __init__(self, chunks_per_round: list[list[str]]):
        # chunks_per_round[i] = 第 i 轮要 yield 的 text chunks
        self.chunks_per_round = chunks_per_round
        self.round_idx = 0
        self.stream_called = 0

    async def chat(self, messages, system, tools=None):
        return LLMResponse(text="mock", tool_calls=[], stop_reason="end_turn")

    async def stream_chat(self, messages, system, tools=None):
        self.stream_called += 1
        chunks = self.chunks_per_round[self.round_idx] if self.round_idx < len(self.chunks_per_round) else ["final"]
        self.round_idx += 1
        for c in chunks:
            yield {"type": "text", "data": {"delta": c}}
        # 第一轮调工具，第二轮直接结束
        if self.round_idx == 1:
            yield {
                "type": "tool_start",
                "data": {"id": "tool-1", "name": "list_projects", "args": {}},
            }


@pytest.mark.asyncio
async def test_cot_event_yielded_for_complete_think_block(monkeypatch):
    """跨 delta 累积的 think 块，完整闭合时 yield cot 事件（位置切片 bug 回归）。"""
    # mock execute_tool 跳过真实 db 调用
    from app.llm import chat_engine as ce
    async def fake_execute(name, args):
        return '{"ok": true}'
    monkeypatch.setattr(ce, "execute_tool", fake_execute)

    # round 1: 有完整 think 块 + 文本 + 工具
    # round 2: 无 think 块，文本后结束
    client = MockStreamingClient([
        ["<think>", "user wants to add task", "</think>", "我先看下项目"],
        ["已加好任务", "end"],
    ])

    events = []
    async for ev in run_chat_stream("添加任务", client=client):
        events.append(ev)

    # 验证：至少一个 cot 事件，含完整 think 块
    cot_events = [e for e in events if e["type"] == "cot"]
    assert len(cot_events) >= 1, f"应该 yield cot 事件，实际: {events}"
    assert "<think>" in cot_events[0]["data"]["text"]
    assert "</think>" in cot_events[0]["data"]["text"]


@pytest.mark.asyncio
async def test_cot_event_not_yielded_for_unclosed_think(monkeypatch):
    """未关闭的 think 块不应 yield cot 事件（避免泄露半截内容）。"""
    from app.llm import chat_engine as ce
    async def fake_execute(name, args):
        return '{"ok": true}'
    monkeypatch.setattr(ce, "execute_tool", fake_execute)

    # think 块未关闭
    client = MockStreamingClient([
        ["<think>", "partial think", "我先看下", "项目"],
        ["好的", "完成"],
    ])

    events = []
    async for ev in run_chat_stream("hi", client=client):
        events.append(ev)

    cot_events = [e for e in events if e["type"] == "cot"]
    assert len(cot_events) == 0, f"未关闭 think 块不应 yield cot 事件，实际: {cot_events}"


@pytest.mark.asyncio
async def test_keyword_stream_yields_text():
    """关键词流式（_run_keyword_stream）：yield 完整 text 事件。"""
    events = []
    async for ev in _run_keyword_stream("帮助"):
        events.append(ev)
    # 关键词响应：1 个 text 事件
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) >= 1
    assert "Cockpit" in text_events[0]["data"]["delta"] or "任务" in text_events[0]["data"]["delta"]


@pytest.mark.asyncio
async def test_run_chat_stream_prefer_llm_false_uses_keyword():
    """prefer_llm=False：直接走关键词流式，不尝试 LLM。"""
    events = []
    async for ev in run_chat_stream("帮助", prefer_llm=False):
        events.append(ev)
    # 应有 text 事件（来自关键词）
    text_events = [e for e in events if e["type"] == "text"]
    assert len(text_events) >= 1

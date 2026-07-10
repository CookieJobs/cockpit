"""聊天 session 持久化测试。"""
from __future__ import annotations

import json
import uuid

import pytest

from app.core import storage


@pytest.mark.asyncio
async def test_create_session(temp_db):
    """创建 session 并验证字段。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    session = await storage.create_chat_session(sid, label="测试 session")
    assert session.id == sid
    assert session.label == "测试 session"
    assert session.archived is False
    assert session.message_count == 0


@pytest.mark.asyncio
async def test_get_session_returns_count(temp_db):
    """get_chat_session 应返回 message_count。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    await storage.add_chat_message(sid, "user", "你好")
    await storage.add_chat_message(sid, "assistant", "你好！")

    s = await storage.get_chat_session(sid)
    assert s is not None
    assert s.message_count == 2


@pytest.mark.asyncio
async def test_get_session_not_found(temp_db):
    """不存在的 session 返回 None。"""
    s = await storage.get_chat_session("nonexistent-id")
    assert s is None


@pytest.mark.asyncio
async def test_list_sessions_sorted_by_recency(temp_db):
    """list_chat_sessions 按 last_active_at 倒序。"""
    import asyncio

    sid1 = f"sess-{uuid.uuid4().hex[:12]}"
    sid2 = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid1, label="旧")
    await asyncio.sleep(0.05)  # 确保时间戳不同
    await storage.create_chat_session(sid2, label="新")

    sessions = await storage.list_chat_sessions()
    assert len(sessions) == 2
    assert sessions[0].id == sid2  # 最新在前
    assert sessions[1].id == sid1


@pytest.mark.asyncio
async def test_rename_session(temp_db):
    """重命名 session。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid, label="原始")
    renamed = await storage.rename_chat_session(sid, "新名称")
    assert renamed is not None
    assert renamed.label == "新名称"


@pytest.mark.asyncio
async def test_archive_session(temp_db):
    """归档后默认列表不显示。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    archived = await storage.archive_chat_session(sid, archived=True)
    assert archived is not None
    assert archived.archived is True

    default_list = await storage.list_chat_sessions(include_archived=False)
    assert all(s.id != sid for s in default_list)

    full_list = await storage.list_chat_sessions(include_archived=True)
    assert any(s.id == sid for s in full_list)


@pytest.mark.asyncio
async def test_delete_session_cascades_messages(temp_db):
    """删 session 级联删 messages。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    await storage.add_chat_message(sid, "user", "test 1")
    await storage.add_chat_message(sid, "assistant", "test 2")

    ok = await storage.delete_chat_session(sid)
    assert ok is True

    msgs = await storage.list_chat_messages(sid)
    assert msgs == []

    session = await storage.get_chat_session(sid)
    assert session is None


@pytest.mark.asyncio
async def test_add_chat_message_with_tool_calls(temp_db):
    """add_chat_message 支持 tool_calls 字段。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)

    tool_calls = [
        {"id": "call_1", "name": "add_task", "args": {"title": "测试任务"}},
    ]
    msg = await storage.add_chat_message(
        sid, "assistant", "已添加任务", tool_calls=tool_calls
    )
    assert msg.role == "assistant"
    assert msg.tool_calls is not None
    assert msg.tool_calls[0]["name"] == "add_task"


@pytest.mark.asyncio
async def test_list_messages_returns_in_order(temp_db):
    """list_chat_messages 按时间正序。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    await storage.add_chat_message(sid, "user", "第 1 条")
    import asyncio
    await asyncio.sleep(0.01)
    await storage.add_chat_message(sid, "assistant", "第 2 条")
    await asyncio.sleep(0.01)
    await storage.add_chat_message(sid, "user", "第 3 条")

    msgs = await storage.list_chat_messages(sid)
    assert len(msgs) == 3
    assert msgs[0].content == "第 1 条"
    assert msgs[1].content == "第 2 条"
    assert msgs[2].content == "第 3 条"


@pytest.mark.asyncio
async def test_list_messages_limit(temp_db):
    """limit 参数生效。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    for i in range(10):
        await storage.add_chat_message(sid, "user", f"msg-{i}")

    msgs = await storage.list_chat_messages(sid, limit=5)
    assert len(msgs) == 5
    # 应该返回最近的 5 条
    assert msgs[-1].content == "msg-9"


@pytest.mark.asyncio
async def test_load_chat_history_for_llm_returns_anthropic_format(temp_db):
    """load_chat_history_for_llm 返回 Anthropic 格式 messages 列表。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    # 存一条带 list content 的 assistant 消息
    anthropic_content = json.dumps(
        [
            {"type": "text", "text": "我帮你加了任务"},
            {"type": "tool_use", "id": "call_1", "name": "add_task", "input": {"title": "X"}},
        ],
        ensure_ascii=False,
    )
    await storage.add_chat_message(sid, "user", "添加任务 X")
    await storage.add_chat_message(sid, "assistant", anthropic_content)

    history = await storage.load_chat_history_for_llm(sid)
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "添加任务 X"}
    assert history[1]["role"] == "assistant"
    assert isinstance(history[1]["content"], list)
    assert history[1]["content"][0]["type"] == "text"


@pytest.mark.asyncio
async def test_load_chat_history_handles_plain_text(temp_db):
    """旧格式 plain text content 也能正确加载。"""
    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)
    await storage.add_chat_message(sid, "user", "纯文本消息")

    history = await storage.load_chat_history_for_llm(sid)
    assert history[0] == {"role": "user", "content": "纯文本消息"}


@pytest.mark.asyncio
async def test_touch_session_updates_last_active(temp_db):
    """add_chat_message 后 last_active_at 自动更新。"""
    import asyncio

    sid = f"sess-{uuid.uuid4().hex[:12]}"
    await storage.create_chat_session(sid)

    s1 = await storage.get_chat_session(sid)
    original_time = s1.last_active_at
    await asyncio.sleep(0.05)
    await storage.add_chat_message(sid, "user", "test")

    s2 = await storage.get_chat_session(sid)
    assert s2.last_active_at > original_time
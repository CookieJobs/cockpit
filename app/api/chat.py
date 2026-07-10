"""对话 API。

支持两种模式：
1. LLM 模式：完整多轮对话 + tool calling（默认）
2. 关键词模式：无 LLM 时的兜底（自动 fallback）

Session 集成（2026-07）：
- 如果请求带 session_id，后端自动从 db 加载历史（最近 20 轮）
- 对话结束后，自动把 user + assistant 消息持久化到 db
- 前端用 localStorage 存 session_id，跨刷新保留
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import storage
from app.core.chat import dispatch

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    """对话消息。"""
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """对话请求。"""
    text: str
    history: Optional[list[ChatMessage]] = Field(
        None,
        description="（旧字段，向后兼容）显式历史；新代码请用 session_id 让后端自动加载",
    )
    prefer_llm: bool = True
    session_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description="对话 session id。传了之后后端会自动加载历史 + 持久化本轮消息",
    )


class ChatResponse(BaseModel):
    """对话响应。"""
    text: str
    action: Optional[str] = None
    data: Optional[dict] = None
    used_llm: bool = False
    tool_calls: Optional[list[dict]] = None
    session_id: Optional[str] = None
    persisted: bool = False  # 是否成功持久化（仅当 session_id 传了才可能为 True）


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话接口。

    - 默认 LLM 模式，失败自动 fallback 关键词
    - 如果传了 session_id：自动加载最近 20 轮历史 + 持久化本轮
    - 旧版 history 字段仍兼容（向后兼容，新代码请用 session_id）
    """
    # 决定历史来源：session_id 优先
    history_dicts: Optional[list[dict[str, Any]]] = None
    if req.session_id:
        try:
            history_dicts = await storage.load_chat_history_for_llm(
                req.session_id, limit=40  # 40 条 ≈ 20 轮
            )
        except Exception as e:
            logger.warning(f"Failed to load history for session {req.session_id}: {e}")
            history_dicts = None
    elif req.history:
        history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    response = await dispatch(req.text, history=history_dicts, prefer_llm=req.prefer_llm)

    # 持久化到 session
    persisted = False
    if req.session_id:
        try:
            await _persist_chat_turn(
                req.session_id, req.text, response, is_first_user_msg=(not history_dicts)
            )
            persisted = True
        except Exception as e:
            logger.exception(f"Failed to persist chat turn for session {req.session_id}")
            # 不阻塞响应，标记 persisted=False

    return ChatResponse(
        text=response.text,
        action=response.action,
        data=response.data,
        used_llm=response.used_llm,
        tool_calls=response.tool_calls or None,
        session_id=req.session_id,
        persisted=persisted,
    )


async def _persist_chat_turn(
    session_id: str,
    user_text: str,
    response: Any,
    is_first_user_msg: bool = False,
) -> None:
    """持久化一轮 user + assistant 消息。

    优先用 response.messages（Anthropic 格式完整序列）；如果没有就构造最小序列。
    """
    # 1. 先确保 session 存在（首次发消息时可能是新 session）
    existing = await storage.get_chat_session(session_id)
    if not existing:
        await storage.create_chat_session(session_id, label="新对话")
    elif is_first_user_msg and (existing.label == "新对话" or not existing.label):
        # 自动用首条 user 消息生成 label
        label = _auto_label_from_text(user_text)
        await storage.rename_chat_session(session_id, label)

    # 2. 拆 messages → 持久化 user + assistant
    messages = response.messages or []

    # 找到所有 user 消息和最后一个 assistant 消息
    # 约定：response.messages[-1] 必须是 assistant（来自 chat_engine 的 run_chat 逻辑）
    # 我们只持久化最外层的 user + assistant（不持久化中间的 tool_result user 消息，
    # 因为它们和 tool_use 是绑定关系，存盘后下次加载需要完整 tool_use 上下文）

    # 简化策略：user 消息 = req.text；assistant 消息 = response.messages 里最后一个 assistant
    assistant_msg: Optional[dict] = None
    for m in reversed(messages):
        if m.get("role") == "assistant":
            assistant_msg = m
            break

    # user 消息存为纯文本（兼容旧的 history 格式）
    await storage.add_chat_message(session_id, "user", user_text)

    # assistant 消息存为 Anthropic content list（JSON 字符串）
    if assistant_msg is not None:
        content = assistant_msg.get("content")
        if isinstance(content, list):
            content_str = json.dumps(content, ensure_ascii=False)
        else:
            content_str = str(content or response.text)

        # 提取 tool_calls 摘要（用于 UI 展示）
        tool_calls_summary: list[dict] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls_summary.append({
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "args": block.get("input", {}),
                    })

        await storage.add_chat_message(
            session_id, "assistant", content_str, tool_calls=tool_calls_summary or None
        )
    else:
        # 兜底：纯文本 assistant
        await storage.add_chat_message(session_id, "assistant", response.text)


def _auto_label_from_text(text: str) -> str:
    """根据首条 user 消息生成 label。"""
    t = text.strip().replace("\n", " ")
    if len(t) > 30:
        t = t[:27] + "..."
    return t or "新对话"
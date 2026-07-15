"""对话 API。

支持两种模式：
1. LLM 模式：完整多轮对话 + tool calling（默认）
2. 关键词模式：无 LLM 时的兜底（自动 fallback）

Session 集成（2026-07）：
- 如果请求带 session_id，后端自动从 db 加载历史（最近 20 轮）
- 对话结束后，自动把 user + assistant 消息持久化到 db
- 前端用 localStorage 存 session_id，跨刷新保留

流式版本（2026-07-15）：
- POST /api/chat/stream 用 SSE（text/event-stream）边推进边返回事件
- 事件契约见 app.llm.base.StreamEvent 注释
- 持久化在 end 事件前完成（用累积的 full_text + tool_calls_summary）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
    """对话接口（非流式，关键词模式和无 SSE 客户端走这条）。

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


# ===== SSE 流式端点 =====


def _sse_format(event: str, data: dict) -> str:
    """格式化为 SSE 帧（一个 event + 一个 data 行 + 空行结尾）。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话。

    事件流（按出现顺序）：
    - start: { used_llm: true, session_id }
    - text: { delta: "..." }                （多次，累积成完整文本）
    - tool_start: { id, name, args }         （0-N 次，LLM 决定）
    - tool_end: { id, result, ok }           （与 tool_start 一一对应）
    - end: { persisted, usage, tool_calls }  （终止信号，整个流结束）

    任何阶段都可能 emit error: { message }，客户端应立即关闭流。

    持久化策略：等 run_chat_stream 完整结束后再统一持久化（避免流中断
    留下半截消息）。end 事件里的 persisted 字段告诉前端是否成功。
    """
    # 加载历史（与 chat 端点逻辑一致）
    history_dicts: Optional[list[dict[str, Any]]] = None
    if req.session_id:
        try:
            history_dicts = await storage.load_chat_history_for_llm(req.session_id, limit=40)
        except Exception as e:
            logger.warning(f"Failed to load history for stream session {req.session_id}: {e}")
            history_dicts = None
    elif req.history:
        history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    async def event_gen():
        # 起始事件
        yield _sse_format("start", {
            "session_id": req.session_id,
            "used_llm": True,
        })

        # 校验 LLM 客户端
        try:
            from app.llm.chat_engine import run_chat_stream
            from app.llm.router import get_verified_client

            client = await get_verified_client()
        except Exception as e:
            logger.exception("Failed to init LLM client for stream")
            yield _sse_format("error", {"message": f"LLM init failed: {e}"})
            return

        if client is None:
            yield _sse_format("error", {
                "message": "No LLM client available. Configure API key in settings."
            })
            return

        # 累积（用于持久化）
        full_text = ""
        tool_calls_summary: list[dict] = []
        tool_result_by_id: dict[str, str] = {}

        try:
            async for event in run_chat_stream(
                req.text, history=history_dicts, client=client
            ):
                etype = event.get("type")
                # 透传
                yield _sse_format(etype, event.get("data", {}))
                # 累积
                if etype == "text":
                    full_text += event["data"]["delta"]
                elif etype == "tool_start":
                    tool_calls_summary.append({
                        "id": event["data"]["id"],
                        "name": event["data"]["name"],
                        "args": event["data"].get("args") or {},
                    })
                elif etype == "tool_end":
                    tool_result_by_id[event["data"]["id"]] = event["data"]["result"]
                elif etype == "error":
                    # error 已 emit，直接终止（持久化跳过）
                    return
        except Exception as e:
            logger.exception("Stream run_chat_stream failed")
            yield _sse_format("error", {"message": f"Stream failed: {e}"})
            return

        # 给 tool_calls 补 result_preview
        for tc in tool_calls_summary:
            tid = tc["id"]
            if tid in tool_result_by_id:
                tc["result_preview"] = tool_result_by_id[tid][:200]

        # 持久化
        persisted = False
        if req.session_id:
            try:
                await _persist_chat_turn_stream(
                    req.session_id,
                    user_text=req.text,
                    full_text=full_text,
                    tool_calls_made=tool_calls_summary,
                    is_first_user_msg=(not history_dicts),
                )
                persisted = True
            except Exception as e:
                logger.exception(
                    f"Failed to persist streamed chat turn for session {req.session_id}"
                )

        # 终止事件
        yield _sse_format("end", {
            "persisted": persisted,
            "session_id": req.session_id,
            "text_length": len(full_text),
            "tool_calls": tool_calls_summary or None,
        })

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx buffering
            "Connection": "keep-alive",
        },
    )


async def _persist_chat_turn(
    session_id: str,
    user_text: str,
    response: Any,
    is_first_user_msg: bool = False,
) -> None:
    """持久化一轮 user + assistant 消息（非流式路径用）。

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

        # 提取本轮的 tool_use blocks（用于 UI 在 assistant message 上显示 tool badges）
        tool_calls_summary: list[dict] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls_summary.append({
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "args": block.get("input", {}),
                    })

        # 如果本轮没调工具，但整个对话过程中调了（response.tool_calls 累积），
        # 也把这些累积的工具调用存进去 —— 这样 UI 切回 session 后能看到
        # 完整的工具调用历史（包括前几轮的 add_task / list_projects 等）。
        if not tool_calls_summary and response.tool_calls:
            tool_calls_summary = [
                {"id": tc.get("id", f"hist-{i}"), "name": tc.get("name", ""), "args": tc.get("args", {})}
                for i, tc in enumerate(response.tool_calls)
            ]

        await storage.add_chat_message(
            session_id, "assistant", content_str, tool_calls=tool_calls_summary or None
        )
    else:
        # 兜底：纯文本 assistant
        await storage.add_chat_message(session_id, "assistant", response.text)


async def _persist_chat_turn_stream(
    session_id: str,
    user_text: str,
    full_text: str,
    tool_calls_made: list[dict],
    is_first_user_msg: bool = False,
) -> None:
    """持久化流式路径的一轮对话。

    简化版：assistant 消息只存纯文本 + tool_calls summary，不存完整
    Anthropic content list（流式路径不重建 messages 结构）。下次加载
    历史时 UI 看到 assistant 消息只有 text + tool_calls 字段，不影响
    显示（ChatWindow 只用这两个字段）。
    """
    existing = await storage.get_chat_session(session_id)
    if not existing:
        await storage.create_chat_session(session_id, label="新对话")
    elif is_first_user_msg and (existing.label == "新对话" or not existing.label):
        label = _auto_label_from_text(user_text)
        await storage.rename_chat_session(session_id, label)

    await storage.add_chat_message(session_id, "user", user_text)
    # assistant 消息：纯文本 + tool_calls summary
    await storage.add_chat_message(
        session_id,
        "assistant",
        full_text,
        tool_calls=tool_calls_made or None,
    )


def _auto_label_from_text(text: str) -> str:
    """根据首条 user 消息生成 label。"""
    t = text.strip().replace("\n", " ")
    if len(t) > 30:
        t = t[:27] + "..."
    return t or "新对话"
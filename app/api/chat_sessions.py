"""对话 session 管理 API。

Session 隔离策略：
- session_id 由前端生成（UUID），存 localStorage
- 跨刷新保留；切换浏览器/隐身模式自动建新 session
- 后端只按 session_id 存，不区分设备
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core import storage
from app.core.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== 请求/响应模型 =====


class CreateSessionRequest(BaseModel):
    """创建 session 的请求。"""
    session_id: str = Field(..., min_length=1, max_length=64, description="客户端生成的 UUID")
    label: Optional[str] = Field(None, max_length=100, description="可选标签（不传则用首条 user message 生成）")


class CreateSessionResponse(BaseModel):
    session: ChatSession
    created: bool  # True=新建，False=已存在


class RenameSessionRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)


class SessionListResponse(BaseModel):
    sessions: list[ChatSession]


class MessageListResponse(BaseModel):
    messages: list[ChatMessage]
    session_id: str


# ===== Session CRUD =====


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(req: CreateSessionRequest):
    """创建新 session。

    - 如果 session_id 已存在，返回 created=False 和现有 session（幂等）
    - 如果不存在，新建并返回
    """
    existing = await storage.get_chat_session(req.session_id)
    if existing:
        return CreateSessionResponse(session=existing, created=False)

    label = (req.label or "新对话")[:100]
    session = await storage.create_chat_session(req.session_id, label=label)
    return CreateSessionResponse(session=session, created=True)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(include_archived: bool = False, limit: int = 50):
    """列出 session（按 last_active_at desc）。"""
    limit = max(1, min(limit, 200))
    sessions = await storage.list_chat_sessions(include_archived=include_archived, limit=limit)
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str):
    """取单个 session 详情（含 message_count）。"""
    session = await storage.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.patch("/sessions/{session_id}", response_model=ChatSession)
async def rename_session(session_id: str, req: RenameSessionRequest):
    """重命名 session。"""
    session = await storage.rename_chat_session(session_id, req.label)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除 session（级联删所有 messages）。"""
    ok = await storage.delete_chat_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"ok": True, "deleted_session_id": session_id}


@router.post("/sessions/{session_id}/archive", response_model=ChatSession)
async def archive_session(session_id: str, archived: bool = True):
    """归档/取消归档。"""
    session = await storage.archive_chat_session(session_id, archived=archived)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


# ===== Messages =====


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def list_messages(session_id: str, limit: int = 40):
    """取 session 的最近 N 条消息（默认 40，≈ 20 轮 user/assistant 交互）。"""
    # 先确认 session 存在
    session = await storage.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    limit = max(1, min(limit, 200))
    msgs = await storage.list_chat_messages(session_id, limit=limit)
    return MessageListResponse(messages=msgs, session_id=session_id)


def _auto_label(first_user_text: str) -> str:
    """根据首条 user 消息自动生成 label。"""
    text = first_user_text.strip().replace("\n", " ")
    if len(text) > 30:
        text = text[:27] + "..."
    return text or "新对话"
"""对话 API。

支持两种模式：
1. LLM 模式：完整多轮对话 + tool calling（默认）
2. 关键词模式：无 LLM 时的兜底（自动 fallback）
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.chat import dispatch

router = APIRouter()


class ChatMessage(BaseModel):
    """对话消息。"""
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """对话请求。"""
    text: str
    history: Optional[list[ChatMessage]] = None
    prefer_llm: bool = True


class ChatResponse(BaseModel):
    """对话响应。"""
    text: str
    action: Optional[str] = None
    data: Optional[dict] = None
    used_llm: bool = False
    tool_calls: Optional[list[dict]] = None


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话接口。

    - 默认 LLM 模式
    - 如果 LLM 不可用（无 key / 后端 down），自动 fallback 关键词解析
    - history 用于多轮对话（仅 LLM 模式有效）
    """
    history_dicts = None
    if req.history:
        history_dicts = [{"role": m.role, "content": m.content} for m in req.history]

    response = await dispatch(req.text, history=history_dicts, prefer_llm=req.prefer_llm)

    return ChatResponse(
        text=response.text,
        action=response.action,
        data=response.data,
        used_llm=response.used_llm,
        tool_calls=response.tool_calls or None,
    )

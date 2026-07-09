"""对话 API（命令解析阶段，LLM 接入前的临时实现）。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.chat import dispatch

router = APIRouter()


class ChatRequest(BaseModel):
    text: str


class ChatResponse(BaseModel):
    text: str
    action: str | None = None
    data: dict | None = None


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    response = await dispatch(req.text)
    return ChatResponse(text=response.text, action=response.action, data=response.data)

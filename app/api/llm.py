"""LLM 状态 / 配置 API。

提供：
- LLM 后端健康检查
- 当前配置信息（脱敏）
- 测试连接
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.llm.router import get_verified_client, get_client, reset_client

router = APIRouter()


class LLMStatus(BaseModel):
    """LLM 状态。"""
    available: bool
    backend: str | None = None
    model: str | None = None
    configured_backend: str
    has_key: bool = False
    error: str | None = None


@router.get("/status", response_model=LLMStatus)
async def get_status():
    """检查当前 LLM 后端状态（带 health check 验证）。"""
    client = await get_verified_client()
    if client is None:
        has_key = bool(settings.anthropic_api_key or settings.openai_api_key)
        return LLMStatus(
            available=False,
            configured_backend=settings.shiguang_llm_backend,
            model=settings.shiguang_llm_model,
            has_key=has_key,
        )
    return LLMStatus(
        available=True,
        backend=client.__class__.__name__,
        model=client.model,
        configured_backend=settings.shiguang_llm_backend,
        has_key=True,
    )


@router.post("/test")
async def test_connection():
    """测试 LLM 连接（发一个最小请求）。"""
    client = await get_verified_client()
    if client is None:
        raise HTTPException(503, "No LLM client available. Check API key configuration.")
    ok = await client.health_check()
    return {"ok": ok, "backend": settings.shiguang_llm_backend, "model": client.model}


@router.post("/reset")
async def reset():
    """重置 LLM 客户端缓存（配置变更后用）。"""
    reset_client()
    return {"ok": True}

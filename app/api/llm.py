"""LLM 状态 / 配置 API。

提供：
- LLM 后端健康检查
- 当前配置信息（脱敏）
- 测试连接
- polish_cv: 完成任务时把 outcome 润色成 CV 风格（2026-07-28 立）
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.llm.base import text_message
from app.llm.router import get_verified_client, get_client, reset_client

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== polish_cv =====

POLISH_CV_SYSTEM = """你是简历润色助手。把用户给的「结果描述」改写成 1 句简历级别的成就陈述。

要求：
- 动词开头（如「设计/重构/修复/推动/主导」）
- 含具体成果或影响（量化优先：DAU 提升 5%、节省 2 小时/天、上线 3 个模块等）
- 不超过 80 字，不超过 1 句
- 保持事实：只能基于用户提供的素材，绝不编造数据/影响
- 不要 emoji 不要 markdown 不要引号，只输出纯文本

如果用户描述太抽象（"做完了"、"搞定了"），返回「完成「{task_title}」」即可，不要硬编。"""


class PolishCvRequest(BaseModel):
    """polish_cv 请求。"""
    task_title: str = Field(..., min_length=1, max_length=500, description="任务标题（兜底句会用）")
    outcome: str = Field(..., min_length=1, max_length=2000, description="用户填的「结果描述」")


class PolishCvResponse(BaseModel):
    """polish_cv 响应。polished=false 表示走了 fallback（无 LLM / LLM 失败）。"""
    cv: str
    polished: bool


def _fallback_cv(task_title: str) -> str:
    """LLM 不可用时的兜底（跟 CompleteTaskModal 默认值一致）。"""
    return f"完成「{task_title}」"


@router.post("/polish_cv", response_model=PolishCvResponse)
async def polish_cv(req: PolishCvRequest):
    """把 outcome 润色成 CV 风格的成就陈述。

    设计目标（2026-07-28 立）：
    - 完成弹窗只剩 outcome 1 个必填字段，cv 智能生成
    - 用户不想润色也能直接用「完成「{title}」」兜底
    - LLM 不可用时静默 fallback，不抛 500（避免润色失败把整个完成流程堵死）
    """
    fallback = _fallback_cv(req.task_title)
    client = await get_verified_client()
    if client is None:
        return PolishCvResponse(cv=fallback, polished=False)

    try:
        resp = await client.chat(
            messages=[
                text_message(
                    "user",
                    f"任务标题：{req.task_title}\n结果描述：{req.outcome}",
                ),
            ],
            system=POLISH_CV_SYSTEM,
            tools=None,  # 不需要 tool calling，纯文本生成
        )
    except Exception as e:
        logger.warning(f"polish_cv: LLM call failed, falling back: {e}")
        return PolishCvResponse(cv=fallback, polished=False)

    if resp.stop_reason == "error" or not resp.text:
        logger.warning(f"polish_cv: LLM returned error/empty, falling back: {resp.error}")
        return PolishCvResponse(cv=fallback, polished=False)

    # 清理 LLM 输出（可能含 markdown 引号 / 句末句号等）
    cv = resp.text.strip().strip('"\'""''').strip()
    # 兜底：万一 LLM 输出空（strip 后）也用 fallback
    if not cv:
        return PolishCvResponse(cv=fallback, polished=False)
    # 兜底：截断超长输出（避免 LLM 啰嗦）
    if len(cv) > 200:
        cv = cv[:200].rstrip("，。,. ") + "..."

    return PolishCvResponse(cv=cv, polished=True)


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
            configured_backend=settings.cockpit_llm_backend,
            model=settings.cockpit_llm_model,
            has_key=has_key,
        )
    return LLMStatus(
        available=True,
        backend=client.__class__.__name__,
        model=client.model,
        configured_backend=settings.cockpit_llm_backend,
        has_key=True,
    )


@router.post("/test")
async def test_connection():
    """测试 LLM 连接（发一个最小请求）。"""
    client = await get_verified_client()
    if client is None:
        raise HTTPException(503, "No LLM client available. Check API key configuration.")
    ok = await client.health_check()
    return {"ok": ok, "backend": settings.cockpit_llm_backend, "model": client.model}


@router.post("/reset")
async def reset():
    """重置 LLM 客户端缓存（配置变更后用）。"""
    reset_client()
    return {"ok": True}

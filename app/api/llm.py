"""LLM 状态 / 配置 API。

提供：
- LLM 后端健康检查
- 当前配置信息（脱敏）
- 测试连接
- polish_cv: 完成任务时把 outcome 润色成 CV 风格（2026-07-28 立）
"""
import json
import logging
import re

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

【追问机制 — 2026-07-30 立】
如果用户给的「结果描述」信息不够具体（比如只写了"做完了"、"完成了 PRD"这种动作型描述，
缺乏对谁、解决了什么、有什么影响），你会需要追问 1-2 个关键问题帮用户补全 CV 价值。
针对当前任务标题的特点，给最值得问的 1-2 个问题。
比如：
  - 任务标题是"完成 PRD" → 问"这份是给谁看的？评审结果怎么样？"
  - 任务标题是"修 bug" → 问"影响多少用户？用了多久解决？"
  - 任务标题是"开会" → 问"参与方是谁？输出了什么决策？"

如果信息已经够具体（用户已经主动提了参与方/影响/量化），follow_up_questions 返空数组。

【输出格式 — 2026-07-30 强化版】
【严格禁止】任何"思维链 / 推理过程"前缀（如 <think>...</think>、"让我想想"、解释为什么这样润色等）。
【严格禁止】markdown 包装（如 ```json、> 引用）。
【严格禁止】任何解释性文字 / 自然语言前缀 / 后缀 / 题外话。
【只输出】一个 JSON 对象，【第一个字符必须是 {，最后一个字符必须是 }】：
{
  "cv": "你的润色结果，1 句（不超过 80 字）",
  "follow_up_questions": ["问题1", "问题2"]
}

如果用户描述太抽象（"做完了"、"搞定了"），cv 返「完成「{task_title}」」，
follow_up_questions 必给 1-2 个针对任务标题的追问（不要给泛泛的"补充细节"）。"""


class PolishCvRequest(BaseModel):
    """polish_cv 请求。"""
    task_title: str = Field(..., min_length=1, max_length=500, description="任务标题（兜底句会用）")
    outcome: str = Field(..., min_length=1, max_length=2000, description="用户填的「结果描述」")


class PolishCvResponse(BaseModel):
    """polish_cv 响应。

    字段语义：
    - cv: 润色后的成就陈述 (polished=True) 或 fallback 句 (polished=False)
    - polished: 是否走了真实 LLM 路径
    - follow_up_questions: 当 outcome 信息不够具体时, LLM 主动追问 1-2 个问题帮用户补全 (2026-07-30 立)
      - 数组可能为空 (信息够了不需要追问)
      - LLM 不可用 / 异常 / 输出解析失败时一律返空数组 (防退化)
    """
    cv: str
    polished: bool
    follow_up_questions: list[str] = Field(
        default_factory=list,
        max_length=3,  # 最多 3 个, 防止 LLM 啰嗦
    )


def _fallback_cv(task_title: str) -> str:
    """LLM 不可用时的兜底（跟 CompleteTaskModal 默认值一致）。"""
    return f"完成「{task_title}」"


def _parse_llm_json_output(raw: str) -> tuple[str | None, list[str]]:
    """鲁棒解析 LLM 输出的 JSON (2026-07-30 强化版, lesson #16 衍生)。

    返回 (cv_or_none, follow_up_questions)
    - 解析成功且 cv 非空: (cv, questions)
    - 解析失败 / cv 空: (None, []) — 调用方走整段当 cv + 空 questions 路径

    处理 5 种情况 (按优先级尝试):
    1. LLM 严格返 JSON: 直接解析
    2. LLM 返 ```json ... ``` 代码块: 去掉包装再解析
    3. LLM 返 <think>...</think> CoT 前缀 (M3 / DeepSeek R1 / reasoning model 习惯):
       用正则剥掉 CoT 包装再尝试解析
    4. LLM 返"自然语言前缀 + JSON 块" 或 "JSON 块 + 自然语言后缀":
       用正则提取最外层 {...} 块再解析
    5. 全部失败: 返 (None, []), 调用方走老路径 (整段当 cv + questions=[])
    """
    if not raw:
        return None, []
    s = raw.strip()

    # 步骤 1: 剥 <think>...</think> CoT 包装 (M3 / DeepSeek R1 习惯)
    s = re.sub(r"<think>.*?</think>\s*", "", s, flags=re.DOTALL).strip()
    # 也处理未配对的 <think> (有些 LLM 截断)
    if s.startswith("<think>"):
        s = s.split("</think>", 1)[-1].strip()

    # 步骤 2: 去掉 markdown ```json 包装
    if s.startswith("```"):
        first_nl = s.find("\n")
        last_close = s.rfind("```")
        if first_nl > 0 and last_close > first_nl:
            s = s[first_nl + 1 : last_close].strip()
        elif last_close > 0:
            # 只有一个 ``` 开头, 没有配对结束 — 截到末尾
            s = s[first_nl + 1 :].strip() if first_nl > 0 else s[3:].strip()

    def _extract(obj: dict) -> tuple[str | None, list[str]] | None:
        """从 dict 提取 cv + questions。无效返 None 让上层继续尝试。"""
        if not isinstance(obj, dict):
            return None
        cv = obj.get("cv")
        questions = obj.get("follow_up_questions", [])
        if not isinstance(cv, str) or not cv.strip():
            return None
        if not isinstance(questions, list):
            questions = []
        questions = [q.strip() for q in questions if isinstance(q, str) and q.strip()][:3]
        return cv.strip(), questions

    # 步骤 3: 严格 JSON 解析
    try:
        result = _extract(json.loads(s))
        if result is not None:
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 步骤 4: 正则提取最外层 {...} 块 (允许 LLM 前后有自然语言)
    # 平衡大括号配对查找
    json_match = _find_balanced_json(s)
    if json_match:
        try:
            result = _extract(json.loads(json_match))
            if result is not None:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None, []


def _find_balanced_json(s: str) -> str | None:
    """在字符串中找最外层平衡的 {...} 块（从第一个 { 开始到对应 }）。
    返回该 JSON 块字符串，找不到返 None。
    """
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        c = s[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


@router.post("/polish_cv", response_model=PolishCvResponse)
async def polish_cv(req: PolishCvRequest):
    """把 outcome 润色成 CV 风格的成就陈述。

    设计目标（2026-07-28 立, 2026-07-30 增 follow_up_questions）：
    - 完成弹窗只剩 outcome 1 个必填字段，cv 智能生成
    - 用户不想润色也能直接用「完成「{title}」」兜底
    - LLM 不可用时静默 fallback，不抛 500（避免润色失败把整个完成流程堵死）
    - 信息不够具体时 LLM 主动追问 1-2 个关键问题, 形成"outcome → 追问 → 补全 → 再润色" 对话闭环
    """
    fallback = _fallback_cv(req.task_title)
    client = await get_verified_client()
    if client is None:
        return PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[])

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
        return PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[])

    if resp.stop_reason == "error" or not resp.text:
        logger.warning(f"polish_cv: LLM returned error/empty, falling back: {resp.error}")
        return PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[])

    # 优先尝试 JSON 解析 (含 follow_up_questions)
    parsed_cv, questions = _parse_llm_json_output(resp.text)
    if parsed_cv is not None:
        # 解析成功: 用 parsed_cv + questions
        cv = parsed_cv
    else:
        # JSON 解析失败: 走老路径 — 整段当 cv + 空 questions (保持向后兼容)
        # 但要先剥 <think> 包装, 避免 CoT 污染 cv (2026-07-30 lesson #16 衍生)
        cv = re.sub(r"<think>.*?</think>\s*", "", resp.text, flags=re.DOTALL).strip()
        if cv.startswith("<think>"):
            cv = cv.split("</think>", 1)[-1].strip()
        cv = cv.strip().strip('"\'""''').strip()
        if not cv:
            return PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[])

    # 兜底：截断超长输出（避免 LLM 啰嗦）
    if len(cv) > 200:
        cv = cv[:200].rstrip("，。,. ") + "..."

    return PolishCvResponse(cv=cv, polished=True, follow_up_questions=questions)


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

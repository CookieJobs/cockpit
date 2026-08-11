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
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.harness.l1 import evaluate_l1
from app.harness.models import (
    AchievementDistillationCase,
    AchievementDistillationInput,
    AchievementDistillationOutput,
)
from app.llm.base import text_message
from app.llm.router import get_verified_client, get_client, reset_client
from app.harness.trace import DistillationTrace, record_trace

logger = logging.getLogger(__name__)

router = APIRouter()


# ===== polish_cv =====

POLISH_CV_SYSTEM = """你是简历润色助手。把用户给的「结果描述」改写成 1 句简历级别的成就陈述, 适合直接贴进简历。

【质量标准 (facts-grounded v1)】
- 以具体动作开头，优先使用：构建/设计/重构/推动/优化/修复/落地/引入/沉淀/实现/搭建/制定/新增/上线/迁移/协调。
- 事实优先于措辞强度：只有用户明确说明主导、独立负责或完成时，才可使用“主导/独立/负责”。【严禁】为了显得强而把“参与、协助、配合、跟进”升级；不得把参与、协助、配合、跟进升级为主导。用户只提供这些表述时，如实保留，或仅改写其已说明的具体动作。不要把“处理、做了、完成”等笼统表述扩写成未提供的职责。
- 含具体成果或影响；量化很有价值，但只能逐字复用用户提供的数字、单位和范围。不得计算或新造百分比、倍数、排名、金额、用户量、团队规模或业务影响（例如不能根据“30 分钟到 5 分钟”自行写“提升 83%”）。没有数字时，使用用户已提供的具体定性事实，不要编造。
- 只有当缺少能让陈述具体化的关键事实时，follow_up_questions 才追问 1-2 个高信息增益问题。用户已提供具体结果时，follow_up_questions 必须为空；不要重复问已有数字、范围或影响。
- 不超过 80 字, 1 句完成
- 保持事实: 只能基于用户提供的素材, 绝不编造数据/影响 (没数据就等追问, 不要瞎编)
- 不要 emoji 不要 markdown 不要引号, 只输出纯文本

【事实优先的改写示例】
以下每个 ✅ 中的事实都必须已经由用户提供；示例不授权你补写数字、范围或 ownership。
❌ 用户只说: "完成了登录 bug 修复"
✅ 可写: "定位并修复登录鉴权 bug，消除用户登录阻塞"（若用户另有提供 “DAU 提升 5%”，才可写入该数字）

❌ 用户只说: "参与了 XX 项目"
✅ 可写: "参与 XX 项目，完成已说明的核心模块设计与交付"（不得改成“主导”，不得补写功能数或用户量）

❌ 用户提供: "重构用户模块，响应从 800ms 降至 200ms"
✅ 可写: "重构用户模块，接口响应时间从 800ms 降至 200ms"（不得自行计算百分比或补写团队效率）

【追问机制 — 2026-07-30 立, v0.3.4 强化】
如果用户给的「结果描述」信息不够具体（缺少完成了什么、实际影响或规模），你会需要追问 1-2 个问题帮用户补全 CV 价值。
优先级: 影响范围 (多少人 / 多大量) > 量化收益 (提升/节省多少) > 团队规模 > 时间成本.
针对当前任务标题的特点, 给最值得问的 1-2 个问题. 比如:
  - 任务标题是"完成 PRD" → 问"这份 PRD 服务的产品/用户量级多大? 评审几轮通过? 推动落地后业务指标怎么变?"
  - 任务标题是"修 bug" → 问"影响多少用户? P0/P1? 用了多久解决? 修复后用户反馈/数据怎么变?"
  - 任务标题是"开会" → 问"参与方都是谁 (级别/角色)? 输出了什么决策? 落地后效果?"
  - 任务标题是"写代码" → 问"这个模块服务多少用户/QPS? 重构前后性能/可维护性指标怎么变?"

如果信息已经够具体（用户已经主动提了参与方、影响或量化），follow_up_questions 返空数组；不得为追求量化而重复追问或假设指标。

【输出格式 — 2026-07-30 强化版】
【严格禁止】任何"思维链 / 推理过程"前缀 (如 <think>...</think>、"让我想想"、解释为什么这样润色等).
【严格禁止】markdown 包装 (如 ```json、> 引用).
【严格禁止】任何解释性文字 / 自然语言前缀 / 后缀 / 题外话.
【只输出】一个 JSON 对象, 【第一个字符必须是 {, 最后一个字符必须是 }】:
{
  "cv": "你的润色结果, 1 句 (不超过 80 字)",
  "follow_up_questions": ["问题1", "问题2"]
}

如果用户描述太抽象 ("做完了"、"搞定了"), cv 返「完成「{task_title}」」,
follow_up_questions 必给 1-2 个针对任务标题的追问 (不要给泛泛的"补充细节")."""


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
    trace_id: str | None = None
    guardrail_results: dict[str, object] = Field(default_factory=dict)


async def _with_distillation_trace(
    req: PolishCvRequest,
    response: PolishCvResponse,
    *,
    started_at: float,
    raw_output: str = "",
    error: str | None = None,
    guardrail_results: dict[str, object] | None = None,
) -> PolishCvResponse:
    """Persist observability without letting audit failure break completion flow."""
    generator_status = "polished" if response.polished else "fallback"
    final_quality_status = "ready" if response.polished and not response.follow_up_questions else "needs_data"
    resolved_guardrails = guardrail_results or _runtime_guardrail_results(req, response)
    response.guardrail_results = resolved_guardrails
    try:
        trace = DistillationTrace.new(
            task_title=req.task_title,
            outcome=req.outcome,
            raw_output=raw_output,
            parsed_output={
                "cv": response.cv,
                "follow_up_questions": response.follow_up_questions,
                "polished": response.polished,
            },
            generator_status=generator_status,
            guardrail_results=resolved_guardrails,
            final_quality_status=final_quality_status,
            model_version="configured-client" if response.polished else "unavailable",
            prompt_version="polish_cv_facts_grounded_v1",
            dataset_version="achievement_distillation_v1",
            harness_version="v1",
            latency_ms=round((time.perf_counter() - started_at) * 1000),
            error=error,
        )
        await record_trace(trace)
        response.trace_id = trace.id
    except Exception as trace_error:
        logger.warning("polish_cv trace persistence failed: %s", trace_error)
    return response


def _runtime_guardrail_results(req: PolishCvRequest, response: PolishCvResponse) -> dict[str, object]:
    """Evaluate P0 provenance checks against the exact runtime context."""
    case = AchievementDistillationCase(
        id="runtime",
        category="boundary",
        input=AchievementDistillationInput(task_title=req.task_title, outcome=req.outcome, language="zh-CN"),
        severity="p0",
    )
    checks = evaluate_l1(
        case,
        AchievementDistillationOutput(
            cv=response.cv,
            follow_up_questions=response.follow_up_questions,
            generator_status="polished" if response.polished else "fallback",
        ),
    )
    return checks.model_dump()


def _has_p0_runtime_violation(guardrails: dict[str, object]) -> bool:
    return bool(
        guardrails["has_unsupported_number"]
        or guardrails["has_unsupported_entity"]
        or guardrails["ownership_violation"]
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
    started_at = time.perf_counter()
    fallback = _fallback_cv(req.task_title)
    client = await get_verified_client()
    if client is None:
        return await _with_distillation_trace(
            req,
            PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[]),
            started_at=started_at,
            error="llm_unavailable",
        )

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
        return await _with_distillation_trace(
            req,
            PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[]),
            started_at=started_at,
            error=type(e).__name__,
        )

    if resp.stop_reason == "error" or not resp.text:
        logger.warning(f"polish_cv: LLM returned error/empty, falling back: {resp.error}")
        return await _with_distillation_trace(
            req,
            PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[]),
            started_at=started_at,
            error=resp.error or "llm_error",
        )

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
            return await _with_distillation_trace(
                req,
                PolishCvResponse(cv=fallback, polished=False, follow_up_questions=[]),
                started_at=started_at,
                raw_output=resp.text,
                error="empty_after_parse",
            )

    # 兜底：截断超长输出（避免 LLM 啰嗦）
    if len(cv) > 200:
        cv = cv[:200].rstrip("，。,. ") + "..."

    response = PolishCvResponse(cv=cv, polished=True, follow_up_questions=questions)
    guardrails = _runtime_guardrail_results(req, response)
    if _has_p0_runtime_violation(guardrails):
        logger.warning("polish_cv runtime guardrail rejected unsupported claim")
        response = PolishCvResponse(
            cv=fallback,
            polished=False,
            follow_up_questions=questions or ["这项工作的实际影响、范围或量化结果是什么？"],
        )
        return await _with_distillation_trace(
            req,
            response,
            started_at=started_at,
            raw_output=resp.text,
            error="runtime_guardrail_rejected",
            guardrail_results=guardrails,
        )

    return await _with_distillation_trace(
        req,
        response,
        started_at=started_at,
        raw_output=resp.text,
    )


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

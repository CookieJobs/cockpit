"""LLM 状态 / 配置 API。

提供：
- LLM 后端健康检查
- 当前配置信息（脱敏）
- 测试连接
- polish_cv: 完成任务时把 outcome 润色成 CV 风格（2026-07-28 立）
- generate_pr: 从 ready 成就生成 GitHub PR 描述 (2026-08-01 立)
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

POLISH_CV_SYSTEM = """你是简历润色助手。把用户给的「结果描述」改写成 1 句简历级别的成就陈述, 适合直接贴进简历。

【质量标准 (v0.3.4 立, 2026-08-02 升级)】
- 动词开头, 必须用强动作动词: 构建/设计/重构/推动/主导/优化/修复/落地/引入/沉淀/实现/搭建/制定/抽象/设计/打造
- 【严禁】弱动词开头: 负责/参与/协助/处理/做了/搞了/弄了/搞定了/完成 (除非后接具体数字) — 这些是低价值词, 体现不出独特贡献
- 含具体成果或影响 — 【量化是硬指标】: DAU 提升 X%、节省 X 小时/天、上线 X 个模块、覆盖 X 万用户、影响 X 个核心场景、推动 X 个团队协同
- 如果用户描述里没量化, follow_up_questions 必追问 1-2 个量化问题 (没量化 = cv 没价值, 追问是给用户补全的机会)
- 不超过 80 字, 1 句完成
- 保持事实: 只能基于用户提供的素材, 绝不编造数据/影响 (没数据就等追问, 不要瞎编)
- 不要 emoji 不要 markdown 不要引号, 只输出纯文本

【强 vs 弱对比示例 (v0.3.4 新增 few-shot)】
❌ 弱: "完成了登录 bug 修复"
✅ 强: "定位并修复登录鉴权高优先级 bug, 消除用户登录阻塞, DAU 提升 5%"

❌ 弱: "参与了 XX 项目"
✅ 强: "主导 XX 项目核心模块设计, 落地 3 个关键功能, 服务日均 50 万用户"

❌ 弱: "做了 PRD 撰写"
✅ 强: "撰写并推动落地 XX 产品 PRD, 评审通过率 100%, 团队 5 人协同推进"

❌ 弱: "重构了用户模块"
✅ 强: "重构用户模块拆分 3 个微服务, 接口响应时间从 800ms 降至 200ms, 团队开发效率提升 30%"

【追问机制 — 2026-07-30 立, v0.3.4 强化】
如果用户给的「结果描述」信息不够具体 (缺数据/影响/规模), 你会需要追问 1-2 个量化问题帮用户补全 CV 价值.
优先级: 影响范围 (多少人 / 多大量) > 量化收益 (提升/节省多少) > 团队规模 > 时间成本.
针对当前任务标题的特点, 给最值得问的 1-2 个问题. 比如:
  - 任务标题是"完成 PRD" → 问"这份 PRD 服务的产品/用户量级多大? 评审几轮通过? 推动落地后业务指标怎么变?"
  - 任务标题是"修 bug" → 问"影响多少用户? P0/P1? 用了多久解决? 修复后用户反馈/数据怎么变?"
  - 任务标题是"开会" → 问"参与方都是谁 (级别/角色)? 输出了什么决策? 落地后效果?"
  - 任务标题是"写代码" → 问"这个模块服务多少用户/QPS? 重构前后性能/可维护性指标怎么变?"

如果信息已经够具体 (用户已经主动提了参与方/影响/量化), follow_up_questions 返空数组.

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


# ===== generate_pr (2026-08-01 立) =====


class GeneratePrAchievement(BaseModel):
    """PR 描述生成输入的单条成就。"""
    title: str
    cv: str = ""
    outcome: str = ""


class GeneratePrRequest(BaseModel):
    """PR 描述生成请求 (2026-08-01 立)。

    字段:
    - project_name: 项目名 (用于 PR 标题, e.g. "[项目名] 新功能")
    - achievements: N 条 ready 成就 (cv + outcome + title)
    - template_kind: PR_Feature / PR_Bugfix / PR_Refactor
    """
    project_name: str = Field(..., min_length=1, max_length=200)
    achievements: list[GeneratePrAchievement] = Field(..., min_length=1)
    template_kind: str = Field("PR_Feature", description="PR_Feature / PR_Bugfix / PR_Refactor")


class GeneratePrResponse(BaseModel):
    """PR 描述生成响应。

    字段:
    - markdown: 4 段 markdown 文本 (背景/改动/影响/测试)
    - polished: 是否走了真实 LLM 路径 (False = fallback 纯模板)
    """
    markdown: str
    polished: bool


# PR 描述生成的 system prompt (2026-08-01 立)
PR_GENERATION_SYSTEM = """你是 GitHub PR 描述生成助手。

根据用户提供的项目名 + N 条 ready 成就 (cv/outcome), 生成 4 段 markdown PR 描述:
1. **背景** (1-3 句) — 为什么做这个改动? 用户痛点 / 业务背景
2. **改动** (主要 bullet 列表) — 具体做了哪些事? 每条 1 行, 用 achievement 的 cv 作骨架
3. **影响** (1-3 句) — 上线后效果? 用户/业务影响 (e.g. DAU/转化/用户反馈)
4. **测试** (1-2 句) — 怎么验证? 单元测试 / 回归测试 / 灰度

模板类型:
- PR_Feature: 新功能, 重点在"用户价值"
- PR_Bugfix: 修 bug, 重点在"根因 + 影响范围"
- PR_Refactor: 重构/性能, 重点在"性能指标 / 可维护性"

要求:
- 用中文 (用户主要用中文)
- 直接给 markdown, 不要 ```markdown 包装, 不要 "以下是..." 前缀
- 背景段用 1-3 句话, 不要堆成就标题
- 改动段用 bullet list, 每条用 achievement.cv 作骨架
- 影响段用 1-3 句话, 重点量化 (e.g. "上线后 7 天 DAU 提升 5%")
- 测试段用 1-2 句话
- 不要堆砌套话 (e.g. "本次提交非常重要")
- 总长控制在 300-500 字
- 如果 achievement 缺少关键数据 (e.g. 没量化指标), 用 "(请补充具体数字)" 占位

直接输出 4 段 markdown, 不要 JSON 包装。
"""


def _fallback_pr(project_name: str, achievements: list, template_kind: str) -> str:
    """LLM 不可用时的兜底 PR 描述 (纯模板填空)。"""
    bullets = "\n".join(f"- {a.title}" for a in achievements)
    kind_label = {
        "PR_Feature": "新功能",
        "PR_Bugfix": "Bug 修复",
        "PR_Refactor": "重构",
    }.get(template_kind, "新功能")
    return (
        f"## 背景\n\n为 {project_name} 提交{kind_label}:\n\n{bullets}\n\n"
        f"## 改动\n\n(请补充具体实现细节)\n\n"
        f"## 影响\n\n(请补充对用户/业务的影响, e.g. DAU / 转化 / 用户反馈)\n\n"
        f"## 测试\n\n(请补充测试覆盖)\n"
    )


@router.post("/generate_pr", response_model=GeneratePrResponse)
async def generate_pr(req: GeneratePrRequest):
    """从 ready 成就生成 PR 描述 (2026-08-01 立)。

    流程:
    1. 验证 template_kind
    2. 走 LLM 生成 4 段 markdown
    3. LLM 失败/不可用 → 返纯模板填空 (跟 polish_cv 同款兜底)
    4. 返 {markdown, polished}

    跟 polish_cv 同款 CoT 处理 + 截断防啰嗦。
    """
    # 1. 验证 template_kind
    valid_kinds = {"PR_Feature", "PR_Bugfix", "PR_Refactor"}
    if req.template_kind not in valid_kinds:
        raise HTTPException(400, f"Invalid template_kind: {req.template_kind}, must be one of {valid_kinds}")

    fallback = _fallback_pr(req.project_name, req.achievements, req.template_kind)
    client = await get_verified_client()
    if client is None:
        return GeneratePrResponse(markdown=fallback, polished=False)

    # 2. 拼 user prompt
    ach_lines = "\n".join(
        f"- 标题: {a.title}\n  CV: {a.cv or '(无)'}\n  结果: {a.outcome or '(无)'}"
        for a in req.achievements
    )
    user_prompt = (
        f"项目: {req.project_name}\n"
        f"模板类型: {req.template_kind}\n\n"
        f"成就 ({len(req.achievements)} 条):\n{ach_lines}\n\n"
        f"请生成 4 段 PR 描述 markdown。"
    )

    # 3. 调 LLM
    try:
        resp = await client.chat(
            messages=[text_message("user", user_prompt)],
            system=PR_GENERATION_SYSTEM,
            tools=None,
        )
    except Exception as e:
        logger.warning(f"generate_pr: LLM call failed, falling back: {e}")
        return GeneratePrResponse(markdown=fallback, polished=False)

    if resp.stop_reason == "error" or not resp.text:
        logger.warning(f"generate_pr: LLM returned error/empty, falling back: {resp.error}")
        return GeneratePrResponse(markdown=fallback, polished=False)

    # 4. 剥 CoT (lesson #2/#16 衍生)
    md = re.sub(r"<think>.*?</think>\s*", "", resp.text, flags=re.DOTALL).strip()
    if md.startswith("<think>"):
        md = md.split("</think>", 1)[-1].strip()
    # 去掉 markdown 包装
    md = re.sub(r"^```(?:markdown)?\s*\n", "", md, flags=re.MULTILINE)
    md = re.sub(r"\n```\s*$", "", md)
    md = md.strip().strip('"\'""''').strip()

    if not md:
        return GeneratePrResponse(markdown=fallback, polished=False)

    # 5. 截断防啰嗦 (PR 描述目标 300-500 字, 上限 1500)
    if len(md) > 1500:
        md = md[:1500].rstrip("，。,. ") + "..."

    return GeneratePrResponse(markdown=md, polished=True)


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

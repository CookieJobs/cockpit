"""拾光对话引擎：LLM 优先 + 关键词兜底。

调用流程：
1. 尝试 LLM（如果可用）
2. LLM 失败/无 client → 走关键词解析
3. 关键词解析用于离线/无 key 场景

注意：关键词解析器作为 fallback 保留，保证产品在无 LLM 时仍可用。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """对话响应。"""
    text: str
    action: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    used_llm: bool = False
    tool_calls: list[dict[str, Any]] = None  # type: ignore

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []


# ===== 关键词解析器（兜底）=====


Handler = "callable"  # type alias for readability


def _extract_after_keyword(text: str, keywords: list[str]) -> str:
    """从 text 中提取关键词后面的内容。"""
    for kw in keywords:
        if kw in text:
            return text.split(kw, 1)[1].strip().lstrip("：:").strip()
    return ""


async def cmd_focus(text: str) -> ChatResponse:
    snap = await storage.build_snapshot()
    focus = snap.focus
    if not focus:
        return ChatResponse(
            text="🎉 当前没有待办任务。试试说「添加任务 XXX」新建一个吧！",
            action="empty_focus",
        )
    lines = ["**今日聚焦**（按优先级 + 截止日期排序）\n"]
    for i, item in enumerate(focus, 1):
        icon = "🚧" if item.blocked else "▸"
        due = f" · 截止 {item.due}" if item.due else ""
        blocked_tag = " [阻塞中]" if item.blocked else ""
        lines.append(f"{i}. {icon} **{item.title}**{due}{blocked_tag}")
    lines.append(f"\n共 {len(focus)} 项。")
    return ChatResponse(text="\n".join(lines), action="show_focus", data={"count": len(focus)})


async def cmd_add_task(text: str) -> ChatResponse:
    title = _extract_after_keyword(
        text, ["添加任务", "新建任务", "加个任务", "加任务", "创建任务"]
    )
    if not title:
        return ChatResponse(
            text="💡 用法：添加任务 <标题>\n例如：添加任务 修登录 bug",
            action="show_help",
        )
    projects = await storage.list_projects(include_archived=False)
    if not projects:
        project = await storage.add_project(ProjectCreate(name="日常"))
        project_id = project.id
        project_msg = "已自动创建项目「日常」"
    else:
        project_id = projects[0].id
        project_msg = f"已加到项目「{projects[0].name}」"
    task = await storage.add_task(TaskCreate(project=project_id, title=title))
    return ChatResponse(
        text=f"✅ 已添加任务：**{title}**\n{project_msg}（草稿状态，确认后生效）",
        action="task_added",
        data={"task": task.model_dump(mode="json")},
    )


async def cmd_complete(text: str) -> ChatResponse:
    keyword = next((k for k in ["完成了", "做完了", "done", "搞定"] if k in text), "")
    if not keyword:
        return ChatResponse(text="💡 用法：<任务关键词>完成了\n例如：修 bug 完成了")
    task_keyword = text.replace(keyword, "").strip()
    if not task_keyword:
        return ChatResponse(text="💡 用法：<任务关键词>完成了\n例如：修 bug 完成了")
    tasks = await storage.list_tasks()
    matches = [t for t in tasks if task_keyword in t.title]
    if not matches:
        return ChatResponse(text=f"😢 没找到包含「{task_keyword}」的任务")
    if len(matches) > 1:
        titles = "\n".join(f"  - {t.title}" for t in matches[:5])
        return ChatResponse(
            text=f"找到 {len(matches)} 个匹配任务，请更精确：\n{titles}",
            action="ambiguous_match",
        )
    task = matches[0]
    cv = f"完成「{task.title}」"
    achievement = await storage.complete_task(
        task.id, outcome="", reflection="", cv=cv, cv_status=CVStatus.READY,
    )
    return ChatResponse(
        text=f"✨ 已沉淀进成就库\n**{task.title}**\n\nCV: {cv}\n（可在成就库补充细节）",
        action="task_completed",
        data={"achievement": achievement.model_dump(mode="json") if achievement else None},
    )


async def cmd_weekly(text: str) -> ChatResponse:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    items = await storage.list_achievements(since=monday)
    if not items:
        return ChatResponse(text="📭 本周还没有完成的成就。完成一些任务后再来吧！")
    by_project: dict[str, list] = {}
    for a in items:
        by_project.setdefault(a.project, []).append(a)
    lines = [f"## 本周完成（{monday} ~ {today}）\n"]
    for project, achievements in by_project.items():
        lines.append(f"### {project}")
        for a in achievements:
            outcome = a.outcome or a.cv or a.title
            lines.append(f"- {outcome}")
        lines.append("")
    return ChatResponse(
        text="\n".join(lines),
        action="weekly_generated",
        data={"count": len(items), "period": f"{monday} ~ {today}"},
    )


async def cmd_promotion(text: str) -> ChatResponse:
    items = await storage.list_achievements(only_ready=True)
    if not items:
        return ChatResponse(text="📭 成就库里还没有 ready 的成就，先去完成一些任务吧！")
    lines = [f"## 述职材料（共 {len(items)} 项成就）\n"]
    for a in items:
        lines.append(f"### {a.title}")
        if a.outcome:
            lines.append(f"- **结果**：{a.outcome}")
        if a.cv:
            lines.append(f"- **CV 描述**：{a.cv}")
        if a.reflection:
            lines.append(f"- **复盘**：{a.reflection}")
        lines.append("")
    return ChatResponse(
        text="\n".join(lines),
        action="promotion_generated",
        data={"count": len(items)},
    )


async def cmd_confirm(text: str) -> ChatResponse:
    count = await storage.confirm_all_drafts()
    return ChatResponse(
        text=f"✅ 已确认 {count} 个草稿任务",
        action="drafts_confirmed",
    )


async def cmd_help(text: str) -> ChatResponse:
    return ChatResponse(
        text=(
            "🤖 **拾光对话命令**（无 LLM 阶段用关键词匹配，3c 阶段会接 LLM）\n\n"
            "**任务管理**\n"
            "- `我现在该干啥` — 查看今日聚焦\n"
            "- `添加任务 <标题>` — 新建任务（草稿）\n"
            "- `<关键词>完成了` — 完成任务并沉淀成就\n"
            "- `确认` — 确认所有草稿任务\n\n"
            "**复盘 / 报告**\n"
            "- `整理周报` — 本周成就汇总（按项目分组）\n"
            "- `述职` / `复盘` — 述职材料生成（只取 ready）\n"
        ),
        action="show_help",
    )


# 关键词路由表
KEYWORD_ROUTES: list[tuple[list[str], Any]] = [
    (["我现在该干啥", "现在该干啥", "该干啥", "现在做什么", "现在做啥", "focus"], cmd_focus),
    (["添加任务", "新建任务", "加个任务", "加任务", "创建任务"], cmd_add_task),
    (["完成了", "做完了", "done", "搞定"], cmd_complete),
    (["整理周报", "周报", "weekly"], cmd_weekly),
    (["述职", "答辩", "promotion", "复盘"], cmd_promotion),
    (["确认", "confirm"], cmd_confirm),
    (["帮助", "help", "怎么用", "你能做什么"], cmd_help),
]


async def dispatch_keyword(text: str) -> ChatResponse:
    """关键词解析器（无 LLM 时的兜底）。"""
    text_lower = text.strip().lower()
    for keywords, handler in KEYWORD_ROUTES:
        for kw in keywords:
            if kw.lower() in text_lower:
                return await handler(text)
    return await cmd_help(text)


# ===== 主入口 =====


async def dispatch(
    text: str,
    history: list | None = None,
    prefer_llm: bool = True,
) -> ChatResponse:
    """主调度：LLM 优先，失败时关键词兜底。

    Args:
        text: 用户输入
        history: 对话历史（LLM 模式时用）
        prefer_llm: 是否优先 LLM（默认 True）

    Returns:
        ChatResponse
    """
    if prefer_llm:
        try:
            from app.llm.chat_engine import run_chat
            from app.llm.router import get_verified_client

            client = await get_verified_client()
            if client is not None:
                result = await run_chat(text, history=history, client=client)
                if result.error:
                    logger.warning(f"LLM failed, falling back to keyword: {result.error}")
                else:
                    return ChatResponse(
                        text=result.text,
                        action="llm_response",
                        data={
                            "tool_calls_made": result.tool_calls_made,
                            "usage": result.usage,
                        },
                        used_llm=True,
                        tool_calls=result.tool_calls_made,
                    )
        except Exception as e:
            logger.exception("LLM dispatch failed, falling back to keyword")

    # 兜底：关键词
    return await dispatch_keyword(text)

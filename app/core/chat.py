"""简化版对话命令解析器（无 LLM 阶段）。

匹配规则：
- 关键词 + 动作 → 调用对应 API
- 不能识别时返回 help

LLM 接入后会被替换（app/llm/），但接口保持一致。
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Awaitable, Callable, Optional

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate


@dataclass
class ChatResponse:
    """对话响应。"""
    text: str  # 展示给用户的话
    action: Optional[str] = None  # 动作标识（前端可触发高亮/动画）
    data: Optional[dict[str, Any]] = None  # 附加数据


# 命令处理函数签名
Handler = Callable[[str], Awaitable[ChatResponse]]


# 关键词 → 处理器路由表
# 顺序很重要：先匹配具体，再匹配通用
KEYWORD_ROUTES: list[tuple[list[str], Handler]] = []


def register(*keywords: str):
    """注册关键词路由的装饰器。"""
    def decorator(handler: Handler) -> Handler:
        KEYWORD_ROUTES.append((list(keywords), handler))
        return handler
    return decorator


@register("我现在该干啥", "现在该干啥", "该干啥", "现在做什么", "现在做啥", "focus")
async def cmd_focus(text: str) -> ChatResponse:
    """返回今日聚焦 + 建议。"""
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
    lines.append(f"\n共 {len(focus)} 项。" if len(focus) == 5 else f"\n共 {len(focus)} 项。")
    return ChatResponse(text="\n".join(lines), action="show_focus", data={"count": len(focus)})


@register("添加任务", "新建任务", "加个任务", "加任务", "创建任务")
async def cmd_add_task(text: str) -> ChatResponse:
    """从 text 提取任务标题并创建。"""
    title = _extract_after_keyword(
        text, ["添加任务", "新建任务", "加个任务", "加任务", "创建任务"]
    )
    if not title:
        return ChatResponse(
            text="💡 用法：添加任务 <标题>\n例如：添加任务 修登录 bug",
            action="show_help",
        )
    # 用第一个 active project 作为默认
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


@register("完成了", "做完了", "done", "搞定")
async def cmd_complete(text: str) -> ChatResponse:
    """匹配「<任务关键词>完成了」格式。"""
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
        task.id,
        outcome="",
        reflection="",
        cv=cv,
        cv_status=CVStatus.READY,
    )
    return ChatResponse(
        text=f"✨ 已沉淀进成就库\n**{task.title}**\n\nCV: {cv}\n（可在成就库补充细节）",
        action="task_completed",
        data={"achievement": achievement.model_dump(mode="json") if achievement else None},
    )


@register("整理周报", "周报", "weekly")
async def cmd_weekly(text: str) -> ChatResponse:
    """整理本周周报。"""
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


@register("述职", "答辩", "promotion", "复盘")
async def cmd_promotion(text: str) -> ChatResponse:
    """整理述职材料（只取 ready 状态）。"""
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


@register("确认", "confirm")
async def cmd_confirm(text: str) -> ChatResponse:
    count = await storage.confirm_all_drafts()
    return ChatResponse(
        text=f"✅ 已确认 {count} 个草稿任务",
        action="drafts_confirmed",
    )


@register("帮助", "help", "怎么用", "你能做什么")
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


async def dispatch(text: str) -> ChatResponse:
    """调度：匹配关键词 → 调用处理器。"""
    text_lower = text.strip().lower()
    for keywords, handler in KEYWORD_ROUTES:
        for kw in keywords:
            if kw.lower() in text_lower:
                return await handler(text)
    return cmd_help(text)


def _extract_after_keyword(text: str, keywords: list[str]) -> str:
    """从 text 中提取关键词后面的内容。"""
    for kw in keywords:
        if kw in text:
            return text.split(kw, 1)[1].strip().lstrip("：:").strip()
    return ""

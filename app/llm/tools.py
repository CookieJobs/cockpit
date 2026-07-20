"""Function Calling 工具注册表。

把Cockpit的核心操作（CRUD、focus、achievements、export）暴露为 LLM 工具。
LLM 通过 function calling 主动调用这些工具来完成任务管理。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core import storage
from app.core.models import (
    CVStatus,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskUpdate,
    AchievementUpdate,
)


@dataclass
class ToolDef:
    """工具定义：schema + 执行函数。"""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


# ===== 工具实现 =====


async def tool_list_projects() -> list[dict]:
    """列出所有未归档项目。"""
    projects = await storage.list_projects(include_archived=False)
    return [p.model_dump(mode="json") for p in projects]


async def tool_add_project(name: str, description: str = "") -> dict:
    """创建新项目（同名校验：同名已存在则返回 existing，不新建）。

    幂等行为：避免重复建同名项目。如果同名项目已存在，返回 existing
    并附加 `_idempotent: true` 标记，让 LLM 知道这是已有项目（用于
    后续 update 或 add_task 到该项目）。
    """
    existing = await storage.list_projects(include_archived=False)
    for p in existing:
        if p.name == name:
            return {"_idempotent": True, **p.model_dump(mode="json")}
    p = await storage.add_project(ProjectCreate(name=name, description=description))
    return p.model_dump(mode="json")


async def tool_update_project(
    id: str,
    name: str | None = None,
    archived: bool | None = None,
    description: str | None = None,
) -> dict:
    p = await storage.update_project(id, ProjectUpdate(name=name, archived=archived, description=description))
    if not p:
        return {"error": f"Project {id} not found"}
    return p.model_dump(mode="json")


async def tool_delete_project(id: str) -> dict:
    """删除项目及其下所有任务（级联）。

    **重要安全**：这是不可逆操作 — 项目和其下所有任务都会被永久删除。
    调用前应 list_projects 确认 id，且建议先告知用户：「将删除项目 X 及其下 N 个任务，确认吗？」。

    如果用户说"这个项目不需要了"/"删掉 X"/"移除 X 项目" → 先 list_projects
    找到 id → **二次确认用户**（对话反问 "确认删除项目 X 吗？"）→ 用户说"是"/"删"/"确认" → 才调本工具。
    """
    proj = await storage.get_project(id)
    if not proj:
        return {"error": f"Project {id} not found"}
    name = proj.name
    # 统计任务数（给用户看删除影响）
    tasks = await storage.list_tasks(project_id=id)
    ok = await storage.delete_project(id)
    if not ok:
        return {"error": f"Failed to delete project {id}"}
    return {
        "ok": True,
        "deleted_project": name,
        "deleted_task_count": len(tasks),
    }


async def tool_list_tasks(project: str | None = None) -> list[dict]:
    """列出任务，可按项目 ID 过滤。"""
    tasks = await storage.list_tasks(project_id=project)
    return [t.model_dump(mode="json") for t in tasks]


async def tool_add_task(
    project: str,
    title: str,
    description: str = "",
    priority: str = "中",
    due: str | None = None,
    blocked: bool = False,
) -> dict:
    """新建任务（直接进 todo）。

    幂等行为：同一项目内，title 严格相等（trim 后）的任务**不会重复建**。
    已存在则返回 existing + `_idempotent: true` 标记，让 LLM 知道这是已有
    任务（用于后续 update_task 改 due/priority/description 等）。
    这是防呆防线 — 即使 LLM 漏掉 list_tasks 检查，也不会建重复任务。
    """
    from app.core.models import Priority
    try:
        prio = Priority(priority)
    except ValueError:
        return {"error": f"Invalid priority: {priority}. Must be 高/中/低."}
    title_clean = title.strip()
    if title_clean:
        existing_tasks = await storage.list_tasks(project_id=project)
        for et in existing_tasks:
            if et.title.strip() == title_clean:
                return {
                    "_idempotent": True,
                    "_hint": "任务已存在。若要修改 due/priority/description 等字段，请用 update_task。",
                    **et.model_dump(mode="json"),
                }
    try:
        t = await storage.add_task(TaskCreate(
            project=project, title=title, description=description, priority=prio,
            due=due, blocked=blocked,
        ))
    except ValueError as e:
        return {"error": str(e)}
    return t.model_dump(mode="json")


async def tool_update_task(
    id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    due: str | None = None,
    blocked: bool | None = None,
    status: str | None = None,
    draft: bool | None = None,
) -> dict:
    """更新任务字段。"""
    from app.core.models import Priority, TaskStatus
    kwargs: dict[str, Any] = {}
    if title is not None:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if priority is not None:
        try:
            kwargs["priority"] = Priority(priority)
        except ValueError:
            return {"error": f"Invalid priority: {priority}"}
    if status is not None:
        try:
            kwargs["status"] = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}
    if due is not None:
        kwargs["due"] = due
    if blocked is not None:
        kwargs["blocked"] = blocked
    if draft is not None:
        kwargs["draft"] = draft
    t = await storage.update_task(id, TaskUpdate(**kwargs))
    if not t:
        return {"error": f"Task {id} not found"}
    return t.model_dump(mode="json")


async def tool_delete_task(id: str) -> dict:
    """删除任务。"""
    ok = await storage.delete_task(id)
    return {"ok": ok, "id": id}


async def tool_confirm_drafts() -> dict:
    """确认所有草稿任务。"""
    count = await storage.confirm_all_drafts()
    return {"confirmed": count}


async def tool_complete_task(
    id: str,
    outcome: str = "",
    reflection: str = "",
    cv: str = "",
    cv_status: str = "ready",
) -> dict:
    """完成任务并沉淀为成就。

    必传参数：
    - id: 任务 ID
    - outcome: 用户描述的结果（必填）
    - cv: agent 生成的 CV 描述（必填，agent 必须根据 outcome+reflection+context 生成）
    - cv_status: "ready"（素材充分）/ "pending"（素材不足，挂起待补）

    可选：
    - reflection: 用户复盘反思（可选）
    """
    try:
        status = CVStatus(cv_status)
    except ValueError:
        return {"error": f"Invalid cv_status: {cv_status}. Must be ready/needs_data/pending."}
    a = await storage.complete_task(
        id, outcome=outcome, reflection=reflection, cv=cv, cv_status=status,
    )
    if not a:
        return {"error": f"Task {id} not found"}
    return a.model_dump(mode="json")


async def tool_undo_completion(id: str) -> dict:
    """撤销成就（恢复 task）。"""
    t = await storage.undo_completion(id)
    if not t:
        return {"error": f"Achievement {id} not found"}
    return t.model_dump(mode="json")


async def tool_list_achievements(
    project: str | None = None,
    since: str | None = None,
    only_ready: bool = False,
    cv_status: str | None = None,
) -> dict:
    """列出成就。"""
    from datetime import date
    from app.core.models import CVStatus
    since_date = date.fromisoformat(since) if since else None
    status_filter: CVStatus | None = None
    if cv_status is not None:
        try:
            status_filter = CVStatus(cv_status)
        except ValueError:
            return {"error": f"Invalid cv_status: {cv_status}"}
    items = await storage.list_achievements(
        project_name=project, since=since_date, only_ready=only_ready,
        cv_status=status_filter,
    )
    return {"items": [a.model_dump(mode="json") for a in items], "count": len(items)}


async def tool_update_achievement(id: str, cv: str | None = None, cv_status: str | None = None) -> dict:
    """更新成就的 CV 字段（用于 pending → ready 升级）。"""
    kwargs: dict[str, Any] = {}
    if cv is not None:
        kwargs["cv"] = cv
    if cv_status is not None:
        try:
            kwargs["cv_status"] = CVStatus(cv_status)
        except ValueError:
            return {"error": f"Invalid cv_status: {cv_status}"}
    a = await storage.update_achievement_cv(id, AchievementUpdate(**kwargs))
    if not a:
        return {"error": f"Achievement {id} not found"}
    return a.model_dump(mode="json")


async def tool_query_snapshot() -> dict:
    """查询全局快照：focus + 项目 + 今日完成 + 计数。"""
    snap = await storage.build_snapshot()
    return snap.model_dump(mode="json")


async def tool_generate_weekly_report() -> str:
    """生成本周周报 markdown（基于本周 ready 成就）。"""
    from datetime import date, timedelta
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    items = await storage.list_achievements(since=monday)
    if not items:
        return "本周还没有完成的成就。"

    by_project: dict[str, list] = {}
    for a in items:
        by_project.setdefault(a.project, []).append(a)

    lines = [f"## 本周完成（{monday} ~ {today}）\n"]
    for proj, list_ in by_project.items():
        lines.append(f"### {proj}")
        for a in list_:
            outcome = a.outcome or a.cv or a.title
            lines.append(f"- {outcome}")
        lines.append("")
    return "\n".join(lines)


# ===== Schema 定义 =====


TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_projects",
        "description": "列出所有未归档的项目。返回项目列表（含 id 和 name）。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_project",
        "description": (
            "创建新项目（同名已存在则返回 existing，不新建）。\n\n"
            "**主动调用**：当用户描述的工作内容明显属于一个新主题/新项目/新场景时，"
            "立即调用此工具建项目，**不要等用户说'创建项目'**。典型触发："
            "'我要做 X'、'接下来要处理 X'、'X 包括 A/B/C'、'我负责的项目是 X'。"
            "**已建同名项目会返回 existing**，不会重复建。"
            "**用户提到已有项目要更新**（如'把项目交接...'）→ 用 update_project，不要新建。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "项目名称（简短）"},
                "description": {"type": "string", "description": "项目描述 / 目标（可选，用户提到的项目背景/目的）"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_project",
        "description": "更新项目（重命名或归档）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "项目 ID"},
                "name": {"type": "string", "description": "新名称"},
                "archived": {"type": "boolean", "description": "是否归档"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_project",
        "description": (
            "删除项目及其下所有任务（**不可逆**）。\n\n"
            "**主动调用场景**（听到这些意图时立即用）：\n"
            "- 「删掉 X 项目」 / 「移除 X 项目」 / 「项目 X 不需要了」 / 「X 项目删了吧」\n"
            "- 「清空 X 项目下的所有任务」 → 删项目比逐个删任务更彻底\n\n"
            "**强制安全流程**：\n"
            "1. 先 `list_projects` 找到目标项目 id\n"
            "2. **对话里反问用户**：「将删除项目 X 及其下 N 个任务，确认吗？」\n"
            "3. 用户明确说「是」/「确认」/「删」**之后**才调本工具\n"
            "4. 返回 `{ok, deleted_project, deleted_task_count}` 告诉用户结果\n\n"
            "**绝不要**用户只说「删」一次就立刻执行 — 删除是不可逆的，必须二次确认。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "项目 ID（必填）"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "list_tasks",
        "description": "列出任务，可按项目 ID 过滤。",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目 ID（可选）"},
            },
            "required": [],
        },
    },
    {
        "name": "add_task",
        "description": (
            "在项目中新建任务。建好立即进入 todo 列表，无需二次确认。\n\n"
            "**主动调用**：当用户描述中提到具体要做的事项（包括子任务、清单、待办），"
            "立即调用此工具建任务，**不要等用户说'添加任务'/'新建任务'**。"
            "典型触发：'包括 A、B、C'、'接下来要做的：1. ... 2. ...'、'我要做 XXX'。"
            "建任务前需要 project_id（先 list_projects 或刚 add_project 拿）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目 ID（必填）"},
                "title": {"type": "string", "description": "任务标题（必填）"},
                "description": {"type": "string", "description": "任务详情 / 上下文（可选）"},
                "priority": {"type": "string", "enum": ["高", "中", "低"], "description": "优先级（默认中）"},
                "due": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                "blocked": {"type": "boolean", "description": "是否被外部阻塞"},
            },
            "required": ["project", "title"],
        },
    },
    {
        "name": "update_task",
        "description": (
            "更新已有任务的字段（**不要用此工具新建**）。\n\n"
            "**主动调用场景**（听到这些意图时立即用）：\n"
            "- 「DDL/截止日期设为 7月12号」 / 「明天截止」 / 「延期到下周」 → `update_task(id, due=\"2026-07-12\")`\n"
            "- 「优先级改成高/中/低」 / 「重要程度调一下」 → `update_task(id, priority=\"高\")`\n"
            "- 「标记为阻塞」 / 「解除阻塞」 → `update_task(id, blocked=true|false)`\n"
            "- 「状态改成进行中/已完成」 → `update_task(id, status=\"IN_PROGRESS\"|\"DONE\")`\n"
            "- 「任务描述补充：...」 / 「任务详情写一下：...」 → `update_task(id, description=\"...\")`\n"
            "- 「任务改名」 → `update_task(id, title=\"...\")`\n\n"
            "**重要**：听到这些意图时，**先 list_tasks 找 id**，再调本工具。**不要 add_task 重建同名任务**。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "任务 ID（必填）"},
                "title": {"type": "string"},
                "description": {"type": "string", "description": "更新任务详情描述"},
                "priority": {"type": "string", "enum": ["高", "中", "低"]},
                "status": {"type": "string", "enum": ["未开始", "进行中", "已完成"]},
                "due": {"type": "string", "description": "YYYY-MM-DD 或 null 清除"},
                "blocked": {"type": "boolean"},
                "draft": {"type": "boolean", "description": "true=待确认 false=已确认"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_task",
        "description": "删除任务（不可恢复，成就不会受影响）。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "任务 ID"}},
            "required": ["id"],
        },
    },
    {
        "name": "confirm_drafts",
        "description": "确认所有 draft 状态的任务，让它们进入 focus 排序。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "complete_task",
        "description": (
            "完成任务并沉淀为成就。\n\n"
            "**重要工作流**：当用户说某事完成时，\n"
            "1. 如果用户已提供 outcome/reflection，直接生成 cv 调用此工具\n"
            "2. 如果素材不充分，cv_status=pending 让用户后续补充\n"
            "3. cv 必须基于 outcome+reflection+任务上下文生成，不能编造"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "任务 ID（必填）"},
                "outcome": {"type": "string", "description": "用户描述的结果（必填）"},
                "reflection": {"type": "string", "description": "用户复盘反思（可选）"},
                "cv": {"type": "string", "description": "agent 生成的 CV 描述（必填，动词开头，含影响/结果）"},
                "cv_status": {"type": "string", "enum": ["ready", "needs_data", "pending"], "description": "ready=素材充分 / needs_data=cv 已写但还差数据 / pending=挂起待补"},
            },
            "required": ["id", "outcome", "cv"],
        },
    },
    {
        "name": "undo_completion",
        "description": "撤销完成（恢复 task 到进行中，删除成就）。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "成就 ID"}},
            "required": ["id"],
        },
    },
    {
        "name": "list_achievements",
        "description": "列出成就，可按项目名/起始日期/只取 ready 过滤。",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目名（不是 ID）"},
                "since": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                "only_ready": {"type": "boolean", "description": "只返回 cvStatus=ready"},
                "cv_status": {"type": "string", "enum": ["ready", "needs_data", "pending"], "description": "按 cv 状态精确过滤（与 only_ready 二选一，cv_status 优先）"},
            },
            "required": [],
        },
    },
    {
        "name": "update_achievement",
        "description": "更新成就的 CV 字段（典型场景：pending → ready 升级）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "成就 ID"},
                "cv": {"type": "string", "description": "新的 CV 描述"},
                "cv_status": {"type": "string", "enum": ["ready", "needs_data", "pending"]},
            },
            "required": ["id"],
        },
    },
    {
        "name": "query_snapshot",
        "description": "查询全局快照：今日 focus（Top 5）、所有项目任务、今日完成、累计计数。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_weekly_report",
        "description": "自动生成本周周报 markdown（按项目分组）。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# 工具名 → 处理器映射
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[Any]]] = {
    "list_projects": tool_list_projects,
    "add_project": tool_add_project,
    "update_project": tool_update_project,
    "delete_project": tool_delete_project,
    "list_tasks": tool_list_tasks,
    "add_task": tool_add_task,
    "update_task": tool_update_task,
    "delete_task": tool_delete_task,
    "confirm_drafts": tool_confirm_drafts,
    "complete_task": tool_complete_task,
    "undo_completion": tool_undo_completion,
    "list_achievements": tool_list_achievements,
    "update_achievement": tool_update_achievement,
    "query_snapshot": tool_query_snapshot,
    "generate_weekly_report": tool_generate_weekly_report,
}


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    """执行工具调用，返回 JSON 字符串结果。"""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        result = await handler(**args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

"""Function Calling 工具注册表。

把Cockpit的核心操作（CRUD、focus、achievements、export）暴露为 LLM 工具。
LLM 通过 function calling 主动调用这些工具来完成任务管理。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.core import storage

# tool_update_task 的 due 参数用 sentinel 区分"未传" vs "传了 None"。
# 普通位置参数默认值是 None, Python 函数签名层面没法靠 `is None` 区分
# "调用者没传" vs "调用者传了 None", 所以用 module-level 单例对象
# 当默认值 (Python 惯用法, PEP 661 sentinel 模式)。
# 用 object() 而不是 str 是为了避免跟任何合法 LLM 输入冲突。
_DUE_UNSET: object = object()
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
    """安全地归档项目；永久删除只能从高级设置的强确认流程完成。"""
    proj = await storage.get_project(id)
    if not proj:
        return {"error": f"Project {id} not found"}
    archived = await storage.update_project(id, ProjectUpdate(archived=True))
    return {"ok": bool(archived), "archived_project": proj.name}


async def tool_list_tasks(project: str | None = None) -> list[dict]:
    """列出任务，可按项目 ID 过滤。"""
    tasks = await storage.list_tasks(project_id=project)
    return [t.model_dump(mode="json") for t in tasks]


async def tool_add_task(
    project: str,
    title: str,
    description: str = "",
    priority: str = "P2",
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
        return {"error": f"Invalid priority: {priority}. Must be P0/P1/P2/P3."}
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
    due: str | None | object = _DUE_UNSET,
    blocked: bool | None = None,
    status: str | None = None,
) -> dict:
    """更新任务字段。

    due 字段特殊处理: 它是 Optional[str], LLM 显式传 `due=null` 表示"清空截止日期"。
    普通位置参数默认值是 None, 没法靠 `is None` 区分"调用者没传" vs "调用者传了 None",
    所以用 module-level sentinel 对象 `_DUE_UNSET` 当默认值 (Python 惯用法):
    - LLM 没传 due 字段 → 走默认值 `_DUE_UNSET` → kwargs 不含 due → storage 不动 due
    - LLM 传 due="2026-08-01" → kwargs["due"] = "2026-08-01" → storage PATCH 设值
    - LLM 传 due=null (显式 None) → kwargs["due"] = None → storage PATCH 清空

    旧版 (修前) `if due is not None: kwargs["due"] = due` 把 None 漏掉, 即便 LLM
    schema 写了 "due: {description: 'YYYY-MM-DD 或 null 清除'}" 也清不掉。
    端到端锁在 app/tests/test_api_patch_due_null.py + tool 层不在测试范围
    (LLM 链路通过对话跑 E2E, 没单测)。
    """
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
    if blocked is not None:
        kwargs["blocked"] = blocked
    # due 单独处理: 用 sentinel `_DUE_UNSET` 区分"未传" vs "传了 None"
    # 默认值是 _DUE_UNSET, LLM 没传 due 就走默认值 → 跳过这个 if, kwargs 不含 due
    # LLM 显式传 None → due is not _DUE_UNSET → kwargs["due"] = None → storage 清空
    # LLM 传字符串 → kwargs["due"] = "2026-08-01" → storage PATCH 设值
    if due is not _DUE_UNSET:
        kwargs["due"] = due

    t = await storage.update_task(id, TaskUpdate(**kwargs))
    if not t:
        return {"error": f"Task {id} not found"}
    return t.model_dump(mode="json")


async def tool_delete_task(id: str) -> dict:
    """删除任务。"""
    ok = await storage.delete_task(id)
    return {"ok": ok, "id": id}


async def tool_complete_task(
    id: str,
    outcome: str = "",
    reflection: str = "",
    cv: str = "",
    cv_status: str = "ready",
    confirmed_cv: bool = False,
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
        id, outcome=outcome, reflection=reflection, cv=cv, cv_status=status, confirmed_cv=confirmed_cv,
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


async def tool_update_achievement(id: str, cv: str | None = None) -> dict:
    """更新成就的 CV 文本；状态由证据补全路径统一推导。"""
    kwargs: dict[str, Any] = {}
    if cv is not None:
        kwargs["cv"] = cv
    a = await storage.update_achievement_cv(id, AchievementUpdate(**kwargs))
    if not a:
        return {"error": f"Achievement {id} not found"}
    return a.model_dump(mode="json")


async def tool_query_snapshot() -> dict:
    """查询全局快照：focus + 项目 + 今日完成 + 计数。"""
    snap = await storage.build_snapshot()
    return snap.model_dump(mode="json")


async def tool_generate_weekly_report() -> str:
    """生成本周周报 markdown（统一 Composer，仅读取 ready 成就）。"""
    from datetime import date, timedelta
    from app.core.composer import ComposeOutputRequest, OutputType, compose_output

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    result = await compose_output(
        ComposeOutputRequest(type=OutputType.WEEKLY, since=monday, until=today)
    )
    return result.markdown


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
            "安全归档项目；永久删除只能在高级设置中完成。\n\n"
            "**主动调用场景**（听到这些意图时立即用）：\n"
            "- 「删掉 X 项目」 / 「移除 X 项目」 / 「项目 X 不需要了」 / 「X 项目删了吧」\n"
            "- 用户坚持永久删除时，说明高级设置会先显示影响、要求精确名称并创建本地备份\n\n"
            "**强制安全流程**：\n"
            "1. 先 `list_projects` 找到目标项目 id\n"
            "2. **对话里反问用户**：「将归档项目 X，确认吗？」\n"
            "3. 用户明确说「是」/「确认」后才调本工具\n"
            "4. 返回归档结果；永久删除不在此工具执行\n\n"
            "**绝不要**用户只说「删」一次就立刻执行。"
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
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "description": "优先级（默认 P2）"},
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
            "- 「优先级改成 P0/P1/P2/P3」 / 「重要程度调一下」 → `update_task(id, priority=\"P0\")`\n"
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
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                "status": {"type": "string", "enum": ["未开始", "进行中", "已完成"]},
                "due": {"type": "string", "description": "YYYY-MM-DD 或 null 清除"},
                "blocked": {"type": "boolean"},
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
        "name": "complete_task",
        "description": (
            "完成任务并沉淀为成就。\n\n"
            "**重要工作流**：当用户说某事完成时，\n"
            "1. 先收集 outcome，并展示候选 CV 与必要追问\n"
            "2. 只有用户明确确认最终 CV 时才传 confirmed_cv=true\n"
            "3. 素材不充分时保存为 needs_data 或 pending，不能声明 ready 绕过确认"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "任务 ID（必填）"},
                "outcome": {"type": "string", "description": "用户描述的结果（必填）"},
                "reflection": {"type": "string", "description": "用户复盘反思（可选）"},
                "cv": {"type": "string", "description": "agent 生成的 CV 描述（必填，动词开头，含影响/结果）"},
                "cv_status": {"type": "string", "enum": ["ready", "needs_data", "pending"], "description": "ready=素材充分 / needs_data=cv 已写但还差数据 / pending=挂起待补"},
                "confirmed_cv": {"type": "boolean", "description": "用户已明确确认最终 CV；未确认时存储层会返回 needs_data 和原因"},
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
        "description": "更新成就的 CV 文字；就绪状态必须通过补全证据自动推导。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "成就 ID"},
                "cv": {"type": "string", "description": "新的 CV 描述"},
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

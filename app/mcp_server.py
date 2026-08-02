"""Cockpit MCP Server (2026-08-02 v0.5a 立).

让 Claude Code / Cursor / 其他 MCP 客户端能调 cockpit:
  - 列出项目/任务
  - 新建项目/任务
  - 完成任务 (走 cockpit 的 4 字段弹窗, 沉淀成就)
  - 查成就库

跑法 (stdio transport, Claude Code / Cursor 默认支持):
    python -m app.mcp_server

或者 (在 Claude Code config):
    {
      "mcpServers": {
        "cockpit": {
          "command": "python",
          "args": ["-m", "app.mcp_server"]
        }
      }
    }

设计 (跟 cockpit 端点一致):
  - 工具 1: list_projects() -> [{id, name, description, archived, ...}]
  - 工具 2: list_tasks(project_id?) -> [{id, title, status, priority, ...}]
  - 工具 3: add_task(project_id, title, priority?, due?) -> {id, ...}
  - 工具 4: complete_task(task_id, outcome, cv) -> {id, cv_status, ...}
  - 工具 5: list_achievements(cv_status?, since?) -> [{id, date, title, cv, ...}]

5 个工具覆盖 cockpit 核心 CRUD — agent 能"看到 → 写 → 完成 → 查沉淀"全链路.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

# 跟 app/main.py 共享: 让 mcp server 跟 web server 用同一个 db
# 强制 unset 一些 web-only 的 env, 避免冲突
os.environ.setdefault("COCKPIT_DISABLE_WEB", "1")

# 重要: 必须在 import app.* 前设置 sys.path, 不然 -m app.mcp_server 可能找不到
# (在 cockpit/ 目录下跑 python -m app.mcp_server 时, cwd 自动进 path)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    ListToolsResult,
    CallToolResult,
)

from app.core import storage
from app.core.models import (
    ProjectCreate,
    TaskCreate,
    TaskStatus,
    CVStatus,
)

logger = logging.getLogger("cockpit.mcp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


# mcp 2.0 API: Server 用 on_list_tools / on_call_tool 作为构造函数参数 (不是装饰器)
# 把 list_tools / call_tool 提到模块顶层, 这样可以传给 Server(...)

async def _handle_list_tools(ctx=None, params=None):
    """mcp 2.0 callback 签名: on_list_tools(ctx, params). 返 ListToolsResult."""
    return ListToolsResult(tools=[
        Tool(
            name="list_projects",
            description="列出 cockpit 所有项目. 用来发现项目 ID (add_task 需要).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_tasks",
            description="列任务, project_id 可选 (None = 全部). 用来发现任务 ID (complete_task 需要).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID (可选)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="add_task",
            description="新建任务. project_id 必填 (从 list_projects 查), title 必填.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "项目 ID"},
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务描述 (可选)"},
                    "priority": {
                        "type": "string",
                        "enum": ["P0", "P1", "P2", "P3"],
                        "description": "优先级 (P0=紧急, P3=不急, 默认 P2)",
                    },
                    "due": {"type": "string", "description": "截止日期 YYYY-MM-DD (可选)"},
                },
                "required": ["project_id", "title"],
            },
        ),
        Tool(
            name="complete_task",
            description=(
                "完成任务并沉淀成就. outcome 必填 (用户描述的结果), cv 必填 (简历级成就陈述, "
                "AI 应该把 outcome 润色成 cv, 用「主导/设计/重构」等强动词开头, "
                "并尽量含量化数据). 完成后成就自动入库, cv_status 可选 ready/needs_data/pending."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "任务 ID (从 list_tasks 查)"},
                    "outcome": {"type": "string", "description": "结果描述 (必填)"},
                    "cv": {"type": "string", "description": "成就陈述 (必填, 简历级)"},
                    "reflection": {"type": "string", "description": "复盘 (可选)"},
                    "cv_status": {
                        "type": "string",
                        "enum": ["ready", "needs_data", "pending"],
                        "description": "成就状态 (默认 ready)",
                    },
                },
                "required": ["task_id", "outcome", "cv"],
            },
        ),
        Tool(
            name="list_achievements",
            description="列成就. cv_status 过滤 ready/needs_data/pending, since 是 YYYY-MM-DD 时间窗起点.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cv_status": {
                        "type": "string",
                        "enum": ["ready", "needs_data", "pending"],
                        "description": "按 cv 状态过滤 (可选)",
                    },
                    "since": {"type": "string", "description": "起始日期 YYYY-MM-DD (可选)"},
                    "project": {"type": "string", "description": "按项目名过滤 (可选)"},
                },
                "required": [],
            },
        ),
    ])


async def _handle_call_tool(ctx=None, params=None):
    """mcp 2.0 callback 签名: on_call_tool(ctx, params). 返 CallToolResult."""
    # params 是 CallToolRequestParams — 含 name + arguments
    name = params.name
    arguments = params.arguments or {}
    try:
        if name == "list_projects":
            result = await _list_projects()
        elif name == "list_tasks":
            result = await _list_tasks(arguments.get("project_id"))
        elif name == "add_task":
            result = await _add_task(
                project_id=arguments["project_id"],
                title=arguments["title"],
                description=arguments.get("description", ""),
                priority=arguments.get("priority", "P2"),
                due=arguments.get("due"),
            )
        elif name == "complete_task":
            result = await _complete_task(
                task_id=arguments["task_id"],
                outcome=arguments["outcome"],
                cv=arguments["cv"],
                reflection=arguments.get("reflection", ""),
                cv_status=arguments.get("cv_status", "ready"),
            )
        elif name == "list_achievements":
            result = await _list_achievements(
                cv_status=arguments.get("cv_status"),
                since=arguments.get("since"),
                project=arguments.get("project"),
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))],
                isError=True,
            )
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))],
        )
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": str(e)}))],
            isError=True,
        )


server = Server(
    "cockpit-mcp",
    version="0.5.0",
    on_list_tools=_handle_list_tools,
    on_call_tool=_handle_call_tool,
)


# ============================================================================
# Tool 1: list_projects
# ============================================================================

async def _list_projects() -> list[dict[str, Any]]:
    """列出所有项目 (含 archived=False, MCP 客户端一般只看活的)."""
    projects = await storage.list_projects(include_archived=False)
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "archived": p.archived,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "sort_order": p.sort_order,
        }
        for p in projects
    ]


# ============================================================================
# Tool 2: list_tasks
# ============================================================================

async def _list_tasks(project_id: Optional[str] = None) -> list[dict[str, Any]]:
    """列任务, project_id 可选 (None = 全部)."""
    tasks = await storage.list_tasks(project_id=project_id)
    return [
        {
            "id": t.id,
            "project": t.project,  # Task schema 用 `project` 字段
            "title": t.title,
            "description": t.description,
            "status": t.status.value if isinstance(t.status, TaskStatus) else str(t.status),
            "priority": t.priority.value if isinstance(t.priority, object) and hasattr(t.priority, "value") else str(t.priority),
            "due": t.due.isoformat() if hasattr(t.due, "isoformat") else t.due,
            "blocked": t.blocked,
            "draft": t.draft,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


# ============================================================================
# Tool 3: add_task
# ============================================================================

async def _add_task(
    project_id: str,
    title: str,
    description: str = "",
    priority: str = "P2",
    due: Optional[str] = None,
) -> dict[str, Any]:
    """新建任务. project_id 用 list_projects 查, priority 是 P0/P1/P2/P3."""
    task_in = TaskCreate(
        project=project_id,
        title=title,
        description=description,
        priority=priority,
        due=due,
    )
    task = await storage.add_task(task_in)
    return {
        "id": task.id,
        "project": task.project,  # Task schema 用 `project` 字段 (不是 project_id)
        "title": task.title,
        "status": task.status.value if isinstance(task.status, TaskStatus) else task.status,
        "priority": task.priority.value if isinstance(task.priority, object) and hasattr(task.priority, "value") else str(task.priority),
    }


# ============================================================================
# Tool 4: complete_task — 跟 web 的"完成弹窗"一致, 沉淀成成就
# ============================================================================

async def _complete_task(
    task_id: str,
    outcome: str,
    cv: str,
    reflection: str = "",
    cv_status: str = "ready",
) -> dict[str, Any]:
    """完成任务. outcome 是必填 (用户描述的结果), cv 是 AI/用户写的成就陈述.

    cv_status:
      - ready: 内容完整, 可用
      - needs_data: 还差数据 (DAU 影响等)
      - pending: 草稿, 之后再补
    """
    # 把 priority 字符串转 enum (storage.add_task 内部会转, 这里直接传)
    achievement = await storage.complete_task(
        task_id=task_id,
        outcome=outcome,
        cv=cv,
        reflection=reflection,
        cv_status=CVStatus(cv_status),
    )
    if achievement is None:
        return {"error": f"Task {task_id} not found"}
    return {
        "id": achievement.id,
        "date": achievement.date.isoformat() if hasattr(achievement.date, "isoformat") else str(achievement.date),
        "task_id": achievement.task_id,
        "project": achievement.project,
        "title": achievement.title,
        "cv": achievement.cv,
        "cv_status": achievement.cv_status.value if isinstance(achievement.cv_status, CVStatus) else achievement.cv_status,
    }


# ============================================================================
# Tool 5: list_achievements
# ============================================================================

async def _list_achievements(
    cv_status: Optional[str] = None,
    since: Optional[str] = None,
    project: Optional[str] = None,
) -> list[dict[str, Any]]:
    """列成就. cv_status 过滤 ready/needs_data/pending, since 是 YYYY-MM-DD."""
    items = await storage.list_achievements(
        project_name=project,
        since=since,
        cv_status=CVStatus(cv_status) if cv_status else None,
    )
    return [
        {
            "id": a.id,
            "date": a.date.isoformat() if hasattr(a.date, "isoformat") else str(a.date),
            "project": a.project,
            "title": a.title,
            "cv": a.cv,
            "cv_status": a.cv_status.value if isinstance(a.cv_status, CVStatus) else a.cv_status,
            "tags": a.tags,
        }
        for a in items
    ]


# ============================================================================
# MCP server 接线
# ============================================================================


async def main():
    # 初始化 cockpit db (跟 web app 一样的 engine)
    db_url = os.environ.get("COCKPIT_DATABASE_URL")
    if db_url:
        storage.init_engine(database_url=db_url)
    else:
        storage.init_engine()  # 用默认 ~/.cockpit/cockpit.db
    await storage.create_tables()

    logger.info("cockpit MCP server starting (stdio transport)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())

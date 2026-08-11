"""Deterministic, local-only career-output composer."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from app.core import storage


class OutputType(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    REVIEW = "review"
    CV = "cv"


class ComposeOutputRequest(BaseModel):
    type: OutputType
    since: date | None = None
    until: date | None = None
    weekly_style: Literal["product", "engineering"] | None = None


class ComposeOutputResponse(BaseModel):
    markdown: str
    ready_achievement_count: int
    needs_attention_count: int
    used_achievement_ids: list[str]


def _grouped_bullets(items) -> list[str]:
    projects: dict[str, list] = {}
    for item in items:
        projects.setdefault(item.project or "未分类", []).append(item)
    lines: list[str] = []
    for project in sorted(projects, key=lambda value: value.casefold()):
        lines.append(f"### {project}")
        for item in projects[project]:
            lines.append(f"- {item.cv or item.outcome or item.title}")
        lines.append("")
    return lines or ["- 本时间范围内没有可直接使用的成果。", ""]


async def compose_output(request: ComposeOutputRequest) -> ComposeOutputResponse:
    """Build an auditable output using storage-owned ready-only data only."""
    ready_items = [
        item for item in await storage.list_output_ready_achievements(since=request.since)
        if item.cv_status.value == "ready"
    ]
    if request.until:
        ready_items = [item for item in ready_items if item.date <= request.until]
    all_items = await storage.list_achievements(since=request.since)
    if request.until:
        all_items = [item for item in all_items if item.date <= request.until]
    tasks = await storage.list_tasks(include_completed=False)
    blocked = [task for task in tasks if task.blocked]
    open_tasks = [task for task in tasks if not task.blocked]

    title_range = "全部时间" if request.since is None else f"{request.since} ~ {request.until or date.today()}"
    bullets = _grouped_bullets(ready_items)
    risks = [f"- {task.title}" for task in blocked] or ["- 暂无已标记的风险或阻塞。"]
    plans = [f"- {task.title}" for task in open_tasks] or ["- 暂无未完成任务。"]

    if request.type == OutputType.WEEKLY:
        lines = [f"## 周报（{title_range}）", "", "### 已完成", *bullets, "### 风险/阻塞", *risks, "", "### 下周计划", *plans]
    elif request.type == OutputType.MONTHLY:
        lines = [f"## 月度总结（{title_range}）", "", "### 关键成果", *bullets, "### 项目进展", *bullets, "### 问题", *risks, "", "### 下月重点", *plans]
    elif request.type == OutputType.REVIEW:
        lines = [f"## 述职材料（{title_range}）", "", "### 核心成果", *bullets, "### 角色与行动", *bullets, "### 证据", *bullets, "### 复盘", "- 基于已确认成果持续补全证据与方法。"]
    else:
        cv_bullets = [f"- {item.cv or item.outcome or item.title}" for item in ready_items]
        lines = ["## 职业成果", "", "### 项目", *bullets, "### 简历成就", *(cv_bullets or ["- 暂无可直接使用的成果。"])]

    return ComposeOutputResponse(
        markdown="\n".join(lines).strip() + "\n",
        ready_achievement_count=len(ready_items),
        needs_attention_count=sum(item.cv_status.value != "ready" for item in all_items),
        used_achievement_ids=[item.id for item in ready_items],
    )

"""Behavioral P0 matrix: all completion/output entrances preserve one boundary."""
from __future__ import annotations

import pytest

from app.core import storage
from app.core.chat import cmd_promotion, cmd_weekly
from app.core.composer import ComposeOutputRequest, OutputType, compose_output
from app.core.models import CVStatus, ProjectCreate, TaskCreate
from app.api.tasks import CompleteTaskRequest, complete_task as web_complete_task
from app.llm.tools import tool_complete_task, tool_generate_weekly_report
from app.mcp_server import _complete_task as mcp_complete_task


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["web_api", "chat_tool", "mcp"])
async def test_same_unconfirmed_completion_evidence_has_same_needs_data_readiness(temp_db, entry):
    project = await storage.add_project(ProjectCreate(name="跨入口"))
    task = await storage.add_task(TaskCreate(project=project.id, title=f"登录鉴权-{entry}"))
    kwargs = {"outcome": "修复登录鉴权问题", "cv": "修复登录鉴权问题", "cv_status": "ready"}

    if entry == "web_api":
        actual = await web_complete_task(task.id, CompleteTaskRequest(**kwargs))
        assert actual["cv_status"] == CVStatus.NEEDS_DATA.value
    elif entry == "chat_tool":
        actual = await tool_complete_task(id=task.id, **kwargs)
        assert actual["cv_status"] == CVStatus.NEEDS_DATA.value
    else:
        actual = await mcp_complete_task(task_id=task.id, **kwargs)
        assert actual["cv_status"] == CVStatus.NEEDS_DATA.value


@pytest.mark.asyncio
async def test_every_formal_output_uses_ready_only_assets_across_composer_and_chat(temp_db):
    project = await storage.add_project(ProjectCreate(name="输出边界"))
    ready_task = await storage.add_task(TaskCreate(project=project.id, title="可用成果"))
    blocked_task = await storage.add_task(TaskCreate(project=project.id, title="待补成果"))
    await storage.complete_task(
        ready_task.id, outcome="交付并获得用户确认", cv="交付并获得用户确认",
        cv_status=CVStatus.READY, confirmed_cv=True,
    )
    await storage.complete_task(
        blocked_task.id, outcome="NEEDS_DATA_SENTINEL", cv="NEEDS_DATA_SENTINEL",
        cv_status=CVStatus.READY,
    )

    composer_outputs = [
        (await compose_output(ComposeOutputRequest(type=kind))).markdown
        for kind in OutputType
    ]
    chat_outputs = [
        (await cmd_weekly("整理周报")).text,
        (await cmd_promotion("述职")).text,
        await tool_generate_weekly_report(),
    ]
    assert all("NEEDS_DATA_SENTINEL" not in output for output in [*composer_outputs, *chat_outputs])

"""Phase 3 deterministic output-composer tests."""
from datetime import date

import pytest

from app.core import storage
from app.core.composer import ComposeOutputRequest, OutputType, compose_output
from app.core.models import Achievement, Priority, Task, TaskStatus


def _achievement(identifier: str, *, status: str = "ready") -> Achievement:
    return Achievement(
        id=identifier, date=date(2026, 8, 10), task_id="task_1", project_id="proj_1",
        project="项目 A", title="交付", outcome="完成交付", cv="确认的成果表述",
        cv_status=status,
    )


@pytest.mark.asyncio
async def test_composer_uses_storage_ready_query_and_not_caller_filtered_list(monkeypatch):
    async def fake_ready_rows(**_kwargs):
        return [_achievement("ready_1")]

    monkeypatch.setattr(storage, "list_output_ready_achievements", fake_ready_rows)
    result = await compose_output(ComposeOutputRequest(type=OutputType.WEEKLY, since=date(2026, 8, 3)))
    assert result.used_achievement_ids == ["ready_1"]
    assert "NEEDS_DATA_SENTINEL" not in result.markdown


@pytest.mark.asyncio
async def test_composer_works_without_llm_and_includes_task_risk_and_next_plan_context(monkeypatch):
    async def fake_ready_rows(**_kwargs):
        return [_achievement("ready_1")]

    async def fake_tasks(**_kwargs):
        return [Task(project="proj_1", title="等待外部依赖", priority=Priority.P1, blocked=True, status=TaskStatus.IN_PROGRESS)]

    monkeypatch.setattr(storage, "list_output_ready_achievements", fake_ready_rows)
    monkeypatch.setattr(storage, "list_tasks", fake_tasks)
    result = await compose_output(ComposeOutputRequest(type=OutputType.WEEKLY))
    assert "风险/阻塞" in result.markdown
    assert "下周计划" in result.markdown


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,sections", [
    (OutputType.WEEKLY, ["已完成", "风险/阻塞", "下周计划"]),
    (OutputType.MONTHLY, ["关键成果", "项目进展", "问题", "下月重点"]),
    (OutputType.REVIEW, ["核心成果", "角色与行动", "证据", "复盘"]),
    (OutputType.CV, ["项目", "简历成就"]),
])
async def test_each_template_is_deterministic_ready_only_and_has_minimum_structure(monkeypatch, kind, sections):
    async def fake_ready_rows(**_kwargs):
        return [_achievement("ready_1"), _achievement("needs_data", status="needs_data")]

    async def fake_tasks(**_kwargs):
        return []

    monkeypatch.setattr(storage, "list_output_ready_achievements", fake_ready_rows)
    monkeypatch.setattr(storage, "list_tasks", fake_tasks)
    result = await compose_output(ComposeOutputRequest(type=kind, since=date(2026, 8, 1), until=date(2026, 8, 31)))
    assert all(section in result.markdown for section in sections)
    assert "NEEDS_DATA_SENTINEL" not in result.markdown

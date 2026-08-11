"""Snapshot readiness counts must describe stored facts without collapsing states."""
import pytest

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate


@pytest.mark.asyncio
async def test_snapshot_counts_each_readiness_state_and_attention_union(temp_db):
    project = await storage.add_project(ProjectCreate(name="计数"))
    tasks = [await storage.add_task(TaskCreate(project=project.id, title=f"任务 {index}")) for index in range(6)]
    statuses = [CVStatus.READY, CVStatus.NEEDS_DATA, CVStatus.NEEDS_DATA, CVStatus.PENDING, CVStatus.PENDING, CVStatus.PENDING]
    for task, status in zip(tasks, statuses):
        await storage.complete_task(
            task.id,
            outcome=f"完成 {task.title} 并记录足够长的结果描述",
            cv=f"完成 {task.title} 并记录足够长的结果描述",
            cv_status=status,
            confirmed_cv=status == CVStatus.READY,
        )

    counts = (await storage.build_snapshot()).counts

    assert counts == {
        "achievementsReady": 1,
        "achievementsNeedsData": 2,
        "achievementsPending": 3,
        "achievementsNeedsAttention": 5,
    }

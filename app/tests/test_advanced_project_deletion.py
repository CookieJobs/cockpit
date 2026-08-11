"""Phase 2 safety regressions for the advanced project-deletion boundary."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import CVStatus, ProjectCreate, TaskCreate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_delete_preview_reports_impact_and_requires_exact_name(client: TestClient):
    project = await storage.add_project(ProjectCreate(name="受保护项目"))
    task = await storage.add_task(TaskCreate(project=project.id, title="已完成任务"))
    for index in range(2):
        await storage.complete_task(
            task.id,
            outcome=f"完成第 {index + 1} 项成果",
            cv=f"完成第 {index + 1} 项成果并确认影响",
            cv_status=CVStatus.READY,
            confirmed_cv=True,
        )

    preview = client.get(f"/api/projects/{project.id}/danger-preview")
    assert preview.status_code == 200
    assert preview.json()["task_count"] == 1
    assert preview.json()["achievement_count"] == 2

    denied = client.post(
        f"/api/projects/{project.id}/danger-delete", json={"project_name": "错误名称"}
    )
    assert denied.status_code == 409
    assert Path(denied.json()["backup_path"]).exists()


@pytest.mark.asyncio
async def test_project_with_achievements_is_archived_not_destroyed(client: TestClient):
    project = await storage.add_project(ProjectCreate(name="需保留资产"))
    task = await storage.add_task(TaskCreate(project=project.id, title="成果任务"))
    await storage.complete_task(
        task.id,
        outcome="交付可验证成果",
        cv="交付可验证成果并确认最终表述",
        cv_status=CVStatus.READY,
        confirmed_cv=True,
    )

    result = client.post(
        f"/api/projects/{project.id}/danger-delete", json={"project_name": project.name}
    )
    assert result.status_code == 409
    assert result.json()["code"] == "achievements_present"
    assert Path(result.json()["backup_path"]).exists()
    assert (await storage.get_project(project.id)) is not None

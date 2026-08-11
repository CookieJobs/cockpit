"""P0 regression tests for evidence-backed achievement readiness."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


async def _create_needs_data_achievement(client: TestClient) -> dict:
    project = await storage.add_project(ProjectCreate(name="登录体验"))
    task = await storage.add_task(TaskCreate(project=project.id, title="修复登录鉴权问题"))
    response = client.post(
        f"/api/tasks/{task.id}/complete",
        json={
            "outcome": "修复登录鉴权问题并恢复用户访问",
            "cv": "修复登录鉴权问题，恢复用户访问",
            "cv_status": "ready",
            "follow_up_questions": ["这次恢复了多少用户访问？"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["cv_status"] == "needs_data"
    return response.json()


@pytest.mark.asyncio
async def test_saving_all_follow_up_answers_does_not_promote_old_cv_to_ready(client: TestClient):
    achievement = await _create_needs_data_achievement(client)

    response = client.patch(
        f"/api/achievements/{achievement['id']}/follow_ups",
        json={"answers": {"0": "恢复了 20 名用户登录"}},
    )

    assert response.status_code == 200, response.text
    assert response.json()["cv_status"] == "needs_data"
    assert "CV 尚未吸收补充证据" in response.json()["unmet_reasons"]


@pytest.mark.asyncio
async def test_resolve_requires_regenerated_confirmed_cv_before_ready(client: TestClient):
    achievement = await _create_needs_data_achievement(client)

    response = client.post(
        f"/api/achievements/{achievement['id']}/resolve",
        json={
            "answers": {"0": "恢复了 20 名用户登录"},
            "cv": "修复登录鉴权问题，恢复 20 名用户登录",
            "distillation_trace_id": "trace_resolution_1",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["cv_status"] == "ready"
    assert response.json()["unmet_reasons"] == []


@pytest.mark.asyncio
async def test_resolve_keeps_unsupported_number_entity_and_ownership_out_of_ready(client: TestClient):
    achievement = await _create_needs_data_achievement(client)

    response = client.post(
        f"/api/achievements/{achievement['id']}/resolve",
        json={
            "answers": {"0": "修复登录鉴权问题"},
            "cv": "主导 5 人团队修复登录鉴权问题，使转化率提升 30%",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["cv_status"] == "needs_data"
    assert "存在无来源事实" in response.json()["unmet_reasons"]


@pytest.mark.asyncio
async def test_direct_cv_edit_rechecks_a_previously_ready_achievement(client: TestClient):
    achievement = await _create_needs_data_achievement(client)
    resolved = client.post(f"/api/achievements/{achievement['id']}/resolve", json={
        "answers": {"0": "恢复了 20 名用户登录"},
        "cv": "修复登录鉴权问题，恢复 20 名用户登录",
    })
    assert resolved.json()["cv_status"] == "ready"

    edited = client.patch(f"/api/achievements/{achievement['id']}", json={
        "cv": "主导 5 人团队修复登录鉴权问题，使转化率提升 30%",
    })

    assert edited.status_code == 200
    assert edited.json()["cv_status"] == "needs_data"
    assert "存在无来源事实" in edited.json()["unmet_reasons"]

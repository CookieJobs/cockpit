"""API 端点测试 — cvStatus 三态（2026-07-20 立 needs_data 中间态）。

锁住:
1. POST /api/tasks/{tid}/complete 接 cv_status="needs_data" 也能正常入库
2. GET /api/achievements?cv_status=needs_data 精确过滤
3. PATCH /api/achievements/{aid} 接 cv_status=needs_data / ready
"""
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


@pytest.mark.asyncio
async def test_api_complete_task_accepts_needs_data(client: TestClient):
    """complete 端点必须接受 needs_data 状态。"""
    p = await storage.add_project(ProjectCreate(name="测试项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="测试任务"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "搞了 X",
            "cv": "主导 X 改版（具体指标待补）",
            "reflection": "",
            "cv_status": "needs_data",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cv_status"] == "needs_data"
    assert "待补" in body["cv"]


@pytest.mark.asyncio
async def test_api_list_achievements_filter_by_cv_status(client: TestClient):
    """list 端点 cv_status 精确过滤。"""
    p = await storage.add_project(ProjectCreate(name="测试项目"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="t1"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="t2"))
    t3 = await storage.add_task(TaskCreate(project=p.id, title="t3"))

    for tid, status in [
        (t1.id, "ready"),
        (t2.id, "needs_data"),
        (t3.id, "pending"),
    ]:
        client.post(
            f"/api/tasks/{tid}/complete",
            json={"outcome": "o", "cv": "c", "cv_status": status},
        )

    # 三个状态分别过滤
    for status, expected_count in [("ready", 1), ("needs_data", 1), ("pending", 1)]:
        res = client.get(f"/api/achievements?cv_status={status}")
        assert res.status_code == 200, res.text
        items = res.json()
        assert len(items) == expected_count, f"cv_status={status} 应返回 1 条"
        assert items[0]["cv_status"] == status


@pytest.mark.asyncio
async def test_api_update_achievement_to_needs_data(client: TestClient):
    """PATCH 端点必须能升级 / 降级 cv_status。"""
    p = await storage.add_project(ProjectCreate(name="测试项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="t"))
    complete_res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={"outcome": "o", "cv": "c", "cv_status": "pending"},
    )
    aid = complete_res.json()["id"]

    # pending → needs_data
    res = client.patch(
        f"/api/achievements/{aid}",
        json={"cv_status": "needs_data"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "needs_data"

    # needs_data → ready
    res = client.patch(
        f"/api/achievements/{aid}",
        json={"cv_status": "ready"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "ready"

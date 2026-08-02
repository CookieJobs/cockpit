"""端点级 + storage 级测试 — 拖动排序 reorder (2026-07-30 立)。

锁住的契约:
1. POST /api/projects/reorder 接受 {items: [{id, sort_order}]} 批量更新
2. POST /api/tasks/reorder 同上, 但**跨项目拒绝** (返回 updated=0)
3. add_project / add_task 自动给新行 sort_order = max+10
4. list_projects / list_tasks 按 sort_order ASC, created_at ASC 排序
5. 不存在的 id 在 reorder 里被静默跳过 (updated 计数正确)
6. 空 items list 是合法 no-op (updated=0)

历史教训 (2026-07-30 立项):
- Lesson 锁定: storage migration 一定要给老数据保持稳定顺序 (created_at fallback)
- Lesson 锁定: 跨项目 reorder 校验是兜底防线, 防 LLM 工具误调
"""
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    return TestClient(app)


# ===== Storage 层测试 =====


@pytest.mark.asyncio
async def test_add_project_assigns_incrementing_sort_order(temp_db):
    """连续 add_project 3 次, sort_order 必须是 0, 10, 20 (max+10 节奏)。"""
    p1 = await storage.add_project(ProjectCreate(name="A"))
    p2 = await storage.add_project(ProjectCreate(name="B"))
    p3 = await storage.add_project(ProjectCreate(name="C"))
    assert p1.sort_order == 0
    assert p2.sort_order == 10
    assert p3.sort_order == 20


@pytest.mark.asyncio
async def test_add_task_increments_within_project(temp_db):
    """任务 sort_order 在项目内递增, 不跨项目污染。"""
    p1 = await storage.add_project(ProjectCreate(name="P1"))
    p2 = await storage.add_project(ProjectCreate(name="P2"))
    t1 = await storage.add_task(TaskCreate(project=p1.id, title="P1-T1"))
    t2 = await storage.add_task(TaskCreate(project=p1.id, title="P1-T2"))
    t3 = await storage.add_task(TaskCreate(project=p2.id, title="P2-T1"))
    t4 = await storage.add_task(TaskCreate(project=p1.id, title="P1-T3"))
    # P1 项目内: 0, 10, 20 (P2 干扰不影响 P1 内部 max)
    assert t1.sort_order == 0
    assert t2.sort_order == 10
    assert t3.sort_order == 0  # P2 第一个 task
    assert t4.sort_order == 20  # P1 第三个 task (max=10+10)


@pytest.mark.asyncio
async def test_list_projects_sorted_by_sort_order_then_created_at(temp_db):
    """list_projects 顺序: sort_order ASC 主, created_at ASC 次。"""
    p1 = await storage.add_project(ProjectCreate(name="A"))
    p2 = await storage.add_project(ProjectCreate(name="B"))
    p3 = await storage.add_project(ProjectCreate(name="C"))
    # 把 p1 拖到最后
    await storage.reorder_projects([{"id": p1.id, "sort_order": 100}])
    projects = await storage.list_projects()
    assert [p.name for p in projects] == ["B", "C", "A"]


@pytest.mark.asyncio
async def test_list_tasks_sorted_within_project(temp_db):
    """list_tasks 项目内按 sort_order ASC, created_at ASC。"""
    p = await storage.add_project(ProjectCreate(name="P"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="T1"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="T2"))
    t3 = await storage.add_task(TaskCreate(project=p.id, title="T3"))
    # 把 t3 拖到最前
    await storage.reorder_tasks([{"id": t3.id, "sort_order": -5}])
    tasks = await storage.list_tasks(project_id=p.id)
    assert [t.title for t in tasks] == ["T3", "T1", "T2"]


@pytest.mark.asyncio
async def test_reorder_projects_updates_only_given_ids(temp_db):
    """reorder_projects 静默跳过不存在的 id, 返回 updated 计数准确。"""
    p1 = await storage.add_project(ProjectCreate(name="A"))
    p2 = await storage.add_project(ProjectCreate(name="B"))
    updated = await storage.reorder_projects([
        {"id": p1.id, "sort_order": 100},
        {"id": "proj_does_not_exist", "sort_order": 50},
    ])
    assert updated == 1
    projects = await storage.list_projects()
    # p1 被推到 100 (最后), p2 保持 10 (前)
    assert projects[-1].id == p1.id


@pytest.mark.asyncio
async def test_reorder_tasks_rejects_cross_project(temp_db):
    """reorder_tasks 跨项目拒绝, 返回 updated=0, 不污染。"""
    p1 = await storage.add_project(ProjectCreate(name="P1"))
    p2 = await storage.add_project(ProjectCreate(name="P2"))
    t1 = await storage.add_task(TaskCreate(project=p1.id, title="P1-T"))
    t2 = await storage.add_task(TaskCreate(project=p2.id, title="P2-T"))
    # 故意构造跨项目的 items
    updated = await storage.reorder_tasks([
        {"id": t1.id, "sort_order": 50},
        {"id": t2.id, "sort_order": 100},
    ])
    assert updated == 0
    # 两个 task 的 sort_order 都没变
    t1_after = await storage.get_task(t1.id)
    t2_after = await storage.get_task(t2.id)
    assert t1_after.sort_order == 0
    assert t2_after.sort_order == 0


@pytest.mark.asyncio
async def test_reorder_tasks_empty_is_noop(temp_db):
    """空 items 是合法 no-op。"""
    updated = await storage.reorder_tasks([])
    assert updated == 0


# ===== 端点级测试 =====


def test_api_reorder_projects_endpoint(client: TestClient):
    """POST /api/projects/reorder 端到端。"""
    p1 = client.post("/api/projects", json={"name": "A"}).json()
    p2 = client.post("/api/projects", json={"name": "B"}).json()
    p3 = client.post("/api/projects", json={"name": "C"}).json()

    res = client.post(
        "/api/projects/reorder",
        json={
            "items": [
                {"id": p3["id"], "sort_order": -10},  # C 拖到最前
                {"id": p1["id"], "sort_order": 50},    # A 拖到最后
                # p2 不动, 保持 10
            ]
        },
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"updated": 2}

    listed = client.get("/api/projects").json()
    assert [p["name"] for p in listed] == ["C", "B", "A"]


def test_api_reorder_tasks_endpoint(client: TestClient):
    """POST /api/tasks/reorder 端到端, 项目内拖动。"""
    p = client.post("/api/projects", json={"name": "P"}).json()
    t1 = client.post("/api/tasks", json={"project": p["id"], "title": "T1"}).json()
    t2 = client.post("/api/tasks", json={"project": p["id"], "title": "T2"}).json()
    t3 = client.post("/api/tasks", json={"project": p["id"], "title": "T3"}).json()

    res = client.post(
        "/api/tasks/reorder",
        json={
            "items": [
                {"id": t3["id"], "sort_order": -5},  # T3 拖到最前
            ]
        },
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"updated": 1}

    listed = client.get(f"/api/tasks?project={p['id']}").json()
    assert [t["title"] for t in listed] == ["T3", "T1", "T2"]


def test_api_reorder_projects_invalid_body(client: TestClient):
    """缺 items 字段必须 422, 不能静默通过。"""
    res = client.post("/api/projects/reorder", json={})
    assert res.status_code == 422


def test_api_reorder_tasks_cross_project_returns_zero(client: TestClient):
    """跨项目 reorder 端点级: 返回 updated=0, 不污染。"""
    p1 = client.post("/api/projects", json={"name": "P1"}).json()
    p2 = client.post("/api/projects", json={"name": "P2"}).json()
    t1 = client.post("/api/tasks", json={"project": p1["id"], "title": "P1-T"}).json()
    t2 = client.post("/api/tasks", json={"project": p2["id"], "title": "P2-T"}).json()

    res = client.post(
        "/api/tasks/reorder",
        json={
            "items": [
                {"id": t1["id"], "sort_order": 100},
                {"id": t2["id"], "sort_order": 200},
            ]
        },
    )
    assert res.status_code == 200
    assert res.json() == {"updated": 0}

    # 两个 task sort_order 都没动
    t1_after = client.get(f"/api/tasks/{t1['id']}").json()
    t2_after = client.get(f"/api/tasks/{t2['id']}").json()
    assert t1_after["sort_order"] == 0
    assert t2_after["sort_order"] == 0

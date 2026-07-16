"""API 端点回归测试 — 锁住"POST body 4 字段"路径。

修复于 2026-07-16:
- /api/tasks/{tid}/complete 之前用 simple type 参数 (str), FastAPI 把它们
  当 query 解析, JSON body 整个被忽略, 全部走默认空值
- 后端 storage.complete_task 入库了 4 字段空字符串的 achievement
- 修法: 改用 Pydantic BaseModel (CompleteTaskRequest) 接 body

这个测试是端点级 (HTTP + FastAPI), 不是 storage 级, 专门锁住这个 bug 不复发。
"""
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    """TestClient + 临时 SQLite DB。"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_api_complete_task_4fields_via_body(client: TestClient):
    """POST 4 字段必须走 body, 不能被 query 吞掉。"""
    # 准备数据
    p = await storage.add_project(ProjectCreate(name="回归测试项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="测试任务"))

    # 关键测试: POST JSON body, 4 字段必须入库
    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "用户反馈登录 bug 已修复, 无复现, DAU 提升 5%",
            "cv": "定位并修复高优先级登录鉴权 bug, 消除用户阻塞, 当日上线验证",
            "reflection": "下次早点拉设计对一遍",
            "cv_status": "ready",
        },
    )
    assert res.status_code == 200, f"complete_task 失败: {res.status_code} {res.text}"
    body = res.json()
    assert body["outcome"] == "用户反馈登录 bug 已修复, 无复现, DAU 提升 5%", \
        f"outcome 没被解析: {body.get('outcome')!r}"
    assert body["cv"].startswith("定位并修复"), f"cv 没被解析: {body.get('cv')!r}"
    assert body["reflection"] == "下次早点拉设计对一遍", f"reflection 没被解析: {body.get('reflection')!r}"
    assert body["cv_status"] == "ready"
    assert body["title"] == "测试任务"
    assert body["project_id"] == p.id

    # task 应该被删除了
    res2 = client.get(f"/api/tasks/{t.id}")
    assert res2.status_code == 404, "task 应该在 complete 后被删除"


@pytest.mark.asyncio
async def test_api_complete_task_pending_status(client: TestClient):
    """cv_status=pending 必须能正常入库, 不被默认 ready 覆盖。"""
    p = await storage.add_project(ProjectCreate(name="P2"))
    t = await storage.add_task(TaskCreate(project=p.id, title="PPT 任务"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "PPT 已完成",
            "cv": "准备并完成演讲 PPT",
            "cv_status": "pending",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cv_status"] == "pending", \
        f"cv_status 没传过去: {body.get('cv_status')!r}"


@pytest.mark.asyncio
async def test_api_complete_task_invalid_cv_status_returns_400(client: TestClient):
    """非法 cv_status 必须 400, 不能被静默接受。"""
    p = await storage.add_project(ProjectCreate(name="P3"))
    t = await storage.add_task(TaskCreate(project=p.id, title="X"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={"outcome": "x", "cv": "y", "cv_status": "wrong_value"},
    )
    assert res.status_code == 400, f"非法 cv_status 应该 400, 实际: {res.status_code}"


@pytest.mark.asyncio
async def test_api_complete_task_default_cv_status_is_ready(client: TestClient):
    """不传 cv_status 应该默认 ready (向后兼容)。"""
    p = await storage.add_project(ProjectCreate(name="P4"))
    t = await storage.add_task(TaskCreate(project=p.id, title="Y"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={"outcome": "x", "cv": "y"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cv_status"] == "ready"

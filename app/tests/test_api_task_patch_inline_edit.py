"""端点级回归测试 — PATCH /api/tasks/{tid} 接受 blocked 字段。

背景 (2026-07-22):
- 用户原则: "凡是 Agent 可以操作的字段, 人也可以操作"
- Agent 与用户都可以通过 ``blocked`` 字段标记或解除外部阻塞。
- 前端 StatusMenu 末尾新增 toggle 入口, 走 PATCH /api/tasks/{tid} + body {blocked: bool}
- 这个测试锁住 API 端点真的能解析 blocked, 不让 FastAPI 静默吞字段

为什么需要这个测试:
- FastAPI 默认对未知 body 字段**不抛错** (它走 Pydantic schema 校验, schema 包含字段就接受)
- TaskUpdate 已经包含 blocked 字段，schema 层 OK
- 但 PATCH 端点必须把 data 真的传到 storage.update_task, 而不是只 echo 回去
- 端点级测试是最后一道防线, 确保 HTTP body 真的端到端
"""
import pytest
from fastapi.testclient import TestClient

from app.core import storage
from app.core.models import ProjectCreate, TaskCreate, TaskUpdate
from app.main import app


@pytest.fixture
def client(temp_db) -> TestClient:
    """TestClient + 临时 SQLite DB。"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_api_patch_blocked_true(client: TestClient):
    """PATCH blocked=true 必须真改数据库, GET 回显必须是 true。"""
    p = await storage.add_project(ProjectCreate(name="PATCH-blocked-true"))
    t = await storage.add_task(TaskCreate(project=p.id, title="被阻塞的活"))

    # 默认 blocked=False
    assert t.blocked is False

    # 用户从 StatusMenu 末尾 toggle "标记阻塞"
    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"blocked": True},
    )
    assert res.status_code == 200, f"PATCH blocked=true 失败: {res.status_code} {res.text}"
    body = res.json()
    assert body["blocked"] is True, (
        f"PATCH 后响应里 blocked 不是 True: {body.get('blocked')!r}, "
        "FastAPI 可能没把 body 字段传到 storage"
    )

    # GET 回查也要是 True, 证明真的入库了, 不只是 echo
    g = client.get(f"/api/tasks/{t.id}")
    assert g.json()["blocked"] is True, (
        "PATCH 后 GET 回查 blocked 不是 True, 说明 storage 层没真存"
    )


@pytest.mark.asyncio
async def test_api_patch_blocked_false_toggle_back(client: TestClient):
    """PATCH blocked=false 必须能 toggle 回 False (双方向, 不只是单向)。"""
    p = await storage.add_project(ProjectCreate(name="PATCH-blocked-false"))
    t = await storage.add_task(TaskCreate(project=p.id, title="先阻塞后解除", blocked=True))

    assert t.blocked is True  # 起点就是 True

    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"blocked": False},
    )
    assert res.status_code == 200
    assert res.json()["blocked"] is False, (
        "用户从 StatusMenu 末尾点'解除阻塞' 后 PATCH blocked=false 必须是 False, "
        "schema 接受 Optional[bool] 但可能某些层把 false 当 None 跳过"
    )

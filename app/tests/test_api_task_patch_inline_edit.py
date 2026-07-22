"""端点级回归测试 — PATCH /api/tasks/{tid} 接受 blocked / draft 字段。

背景 (2026-07-22):
- 用户原则: "凡是 Agent 可以操作的字段, 人也可以操作"
- Agent 通过 tool_update_task(id, blocked=true|false) 和 tool_update_task(id, draft=true|false)
  能改这两个字段 (app/llm/tools.py:168-171)
- 前端 StatusMenu 末尾新增 toggle 入口, 走 PATCH /api/tasks/{tid} + body {blocked: bool}
- 这个测试锁住 API 端点真的能解析 blocked / draft, 不让 FastAPI 静默吞字段

为什么需要这个测试:
- FastAPI 默认对未知 body 字段**不抛错** (它走 Pydantic schema 校验, schema 包含字段就接受)
- TaskUpdate 已经包含 blocked / draft 字段 (app/core/models.py:232-233), schema 层 OK
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


@pytest.mark.asyncio
async def test_api_patch_draft_true(client: TestClient):
    """PATCH draft=true 必须真改数据库, GET 回显必须是 true。

    注意: 用户从 StatusMenu 末尾点"标记草稿" 走的也是这个 API 路径, 跟 Agent 行为一致。
    """
    p = await storage.add_project(ProjectCreate(name="PATCH-draft-true"))
    t = await storage.add_task(TaskCreate(project=p.id, title="待确认的活"))

    assert t.draft is False  # 默认 draft=False

    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"draft": True},
    )
    assert res.status_code == 200, f"PATCH draft=true 失败: {res.status_code} {res.text}"
    assert res.json()["draft"] is True, (
        f"PATCH 后响应里 draft 不是 True: {res.json().get('draft')!r}"
    )

    g = client.get(f"/api/tasks/{t.id}")
    assert g.json()["draft"] is True


@pytest.mark.asyncio
async def test_api_patch_draft_false_confirm(client: TestClient):
    """PATCH draft=false 必须能确认草稿 (这是 confirm_drafts 的单任务版本)。

    StatusMenu 末尾的 "确认草稿" 按钮走这个路径, 跟批量 confirm-drafts 端点互补 —
    - 批量: POST /api/tasks/confirm-drafts (一次性确认所有 draft=True 的)
    - 单个: PATCH /api/tasks/{tid} {"draft": false} (单任务确认, 来自 StatusMenu toggle)
    """
    p = await storage.add_project(ProjectCreate(name="PATCH-draft-false"))
    # TaskCreate 继承 TaskBase, 字段里没有 draft (draft 在 TaskUpdate 里),
    # 所以建任务时没法直接设 draft=True, 需要先建后改
    t = await storage.add_task(TaskCreate(project=p.id, title="草稿待确认"))
    t_drafted = await storage.update_task(t.id, TaskUpdate(draft=True))
    assert t_drafted is not None and t_drafted.draft is True, (
        f"准备阶段 PATCH draft=True 失败, 没法测 PATCH draft=False 路径: {t_drafted!r}"
    )

    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"draft": False},
    )
    assert res.status_code == 200
    assert res.json()["draft"] is False


@pytest.mark.asyncio
async def test_api_patch_blocked_draft_independent(client: TestClient):
    """改 blocked 时不能误改 draft, 反之亦然 (PATCH partial 不串)。"""
    p = await storage.add_project(ProjectCreate(name="PATCH-independence"))
    t = await storage.add_task(TaskCreate(project=p.id, title="两字段独立"))

    # 第一步: 改 blocked
    res1 = client.patch(f"/api/tasks/{t.id}", json={"blocked": True})
    assert res1.status_code == 200
    assert res1.json()["blocked"] is True
    assert res1.json()["draft"] is False, (
        f"PATCH blocked 不该改 draft, 但 draft 变成: {res1.json()['draft']!r}"
    )

    # 第二步: 改 draft
    res2 = client.patch(f"/api/tasks/{t.id}", json={"draft": True})
    assert res2.status_code == 200
    assert res2.json()["draft"] is True
    assert res2.json()["blocked"] is True, (
        "PATCH draft 不该改 blocked, 但 blocked 变成: False (丢阻塞状态)"
    )

"""端点级回归测试 — PATCH /api/tasks/{tid} 接受 due=null 并真正清空 due 字段。

背景 (2026-07-22):
- 用户报 "DueEditor 不能添加/清除截止时间" 两个问题:
  1. 没 due 的任务看不到任何设置入口 (前端 DueEditor 触发 button 漏改 group-hover)
  2. 有 due 的任务只能改不能清空 (后端 storage.update_task 用 `if data.due is not None`
     把 None 当 "未传" 静默吞掉, 加上 LLM 工具 tool_update_task 也用 `if due is not None`
     把 null 过滤掉)
- 修法:
  - 前端 DueEditor 改 popover 模式 + 加 "清除截止日期" 按钮
  - 后端 storage.update_task 用 `data.model_fields_set` 区分 "未传" vs "传了 None"
  - LLM 工具 tool_update_task 改用 **kwargs 收集显式传的 null 字段, 跟 storage 对齐
- 这个测试锁住 PATCH {"due": null} 必须真把 due 字段清空, GET 回显必须是 null
- 锁住 PATCH {"due": "2026-08-01"} 必须能正常设值 (sanity check, 跟 null 路径互斥)

为什么需要这个测试:
- 后端 storage.update_task 旧逻辑 `if data.due is not None: t.due = data.due` 把
  "传了 None = 清空" 跟 "未传" 混为一谈
- 端点级测试是最后一道防线, 端到端走完 HTTP body → Pydantic → storage → SQLAlchemy
  → model_dump 响应, 确保 null 真的能端到端
- LLM 链路 (tool_update_task) 也走同一个 storage, 修 storage 一并修 LLM 链路
- Lesson #3 教训: FastAPI simple type 参数 body 丢失 — Pydantic BaseModel 不会,
  但 storage 层的 `is not None` 判断会。这里锁住修复后的行为。
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
async def test_api_patch_due_null_clears_due(client: TestClient):
    """PATCH {"due": null} 必须真把 due 字段清空 (变 null), 不是 echo。

    端到端:
    - 建任务时设一个 due (走 TaskCreate 的 due 字段)
    - PATCH {"due": null} 模拟前端 "清除截止日期" 按钮
    - 响应里 due 必须是 null (不是 echo 旧值, 不是默认 1970-01-01)
    - GET 回查也必须是 null (证明真入库了, 不只是响应层)
    """
    from datetime import date

    p = await storage.add_project(ProjectCreate(name="PATCH-due-null-clears"))
    t = await storage.add_task(
        TaskCreate(project=p.id, title="有截止日期要清除", due=date(2026, 8, 15))
    )
    assert t.due is not None and str(t.due) == "2026-08-15", (
        f"准备阶段建任务带 due 应该非 null, 实际: {t.due!r}"
    )

    # 前端 DueEditor popover 里点 "清除截止日期" 按钮 → 走这个 PATCH
    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"due": None},
    )
    assert res.status_code == 200, (
        f"PATCH due=null 失败: {res.status_code} {res.text}"
    )
    body = res.json()
    assert body.get("due") is None, (
        f"PATCH 后响应里 due 不是 null: {body.get('due')!r}. "
        "storage.update_task 可能把 None 当 '未传' 静默吞掉, "
        "修法: 改用 data.model_fields_set 区分未传 vs 传了 None"
    )

    # GET 回查也要是 null, 证明真的入库了
    g = client.get(f"/api/tasks/{t.id}")
    assert g.json()["due"] is None, (
        "PATCH 后 GET 回查 due 不是 null, 说明 storage 层没真存. "
        "SQLAlchemy ORM 的 due 列可能没真的被 update"
    )


@pytest.mark.asyncio
async def test_api_patch_due_string_still_works(client: TestClient):
    """PATCH {"due": "2026-08-01"} 必须能正常设值 (sanity check, 跟 null 路径互斥)。

    锁这个是为了防止修复 null 路径时把正常 "设值" 路径搞坏 (过度修复)。
    旧逻辑 `if data.due is not None: t.due = data.due` 对字符串是 OK 的,
    改 `model_fields_set` 后也必须 OK。
    """
    p = await storage.add_project(ProjectCreate(name="PATCH-due-string"))
    t = await storage.add_task(TaskCreate(project=p.id, title="要设截止日期"))
    assert t.due is None  # 起点无 due

    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"due": "2026-08-01"},
    )
    assert res.status_code == 200
    assert res.json()["due"] == "2026-08-01", (
        f"PATCH due='2026-08-01' 后响应里 due 应该是 '2026-08-01', 实际: {res.json().get('due')!r}"
    )

    # GET 回查
    g = client.get(f"/api/tasks/{t.id}")
    assert g.json()["due"] == "2026-08-01"


@pytest.mark.asyncio
async def test_api_patch_without_due_does_not_touch_due(client: TestClient):
    """PATCH 不带 due 字段时不能动 due (无关字段独立)。

    锁住 PATCH 的 "partial" 语义 — 改别的字段 (比如 title) 时不能误清 due。
    这是修 null 路径的副作用风险: `model_fields_set` 改了判断逻辑, 可能把
    "未传 due" 误判成 "传了 None"。
    """
    from datetime import date

    p = await storage.add_project(ProjectCreate(name="PATCH-no-due-field"))
    t = await storage.add_task(
        TaskCreate(project=p.id, title="要改名且保 due", due=date(2026, 9, 10))
    )
    assert str(t.due) == "2026-09-10"

    res = client.patch(
        f"/api/tasks/{t.id}",
        json={"title": "改名了"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "改名了"
    assert body["due"] == "2026-09-10", (
        f"PATCH title 不该动 due, 但 due 变成: {body.get('due')!r}. "
        "model_fields_set 判断可能把 '未传 due' 误判成 '传了 None'"
    )

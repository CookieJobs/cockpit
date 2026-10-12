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
            "confirmed_cv": True,
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

    # 2026-08-01: task 不再删, 改 status=COMPLETED + completed_at=今天
    #   旧版 (v1-v3) 期待 404, 新版 (v4) 期待 200 + status=已完成
    res2 = client.get(f"/api/tasks/{t.id}")
    assert res2.status_code == 200, "task 应该在 complete 后保留 (改 status=已完成, 不删)"
    task_after = res2.json()
    assert task_after["status"] == "已完成", f"task.status 应该是 '已完成', 实际 {task_after['status']!r}"
    assert task_after.get("completed_at") is not None, "task.completed_at 应该是今天"


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
async def test_api_complete_task_confirmed_cv_is_ready(client: TestClient):
    """已确认的 CV 在证据充分时才进入 ready。"""
    p = await storage.add_project(ProjectCreate(name="P4"))
    t = await storage.add_task(TaskCreate(project=p.id, title="Y"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "完成任务并通过线上验收，确认结果符合预期",
            "cv": "完成任务交付并完成线上验收",
            "confirmed_cv": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["cv_status"] == "ready"


@pytest.mark.asyncio
async def test_api_complete_task_defers_ready_until_follow_ups_are_answered(client: TestClient):
    """HTTP 调用也不能把带未答追问的成就写进 ready 输出池。"""
    p = await storage.add_project(ProjectCreate(name="质量门 API"))
    t = await storage.add_task(TaskCreate(project=p.id, title="完成 PRD"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "完成 PRD 撰写并组织评审，确认研发范围和交付节奏",
            "cv": "撰写并评审 PRD，明确研发范围和交付节奏",
            "cv_status": "ready",
            "follow_up_questions": ["影响了哪些核心模块？"],
        },
    )

    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "needs_data"


# ===== 2026-08-23 v0.3 草稿降摩擦: outcome 可空 =====
#
# 背景: 用户报"完成任务时被弹窗卡住", 实际上后端三态 (pending/needs_data/ready)
# 已支持"延后填"。本次 UX 改: outcome 改可选, outcome 完全空 → 后端强制
# cv_status=pending (不走到 needs_data, 因为 outcome 空谈不上"已写 cv 差数据")。
# 这条不动宪法 §2.4, 是 v0.3 沉淀智能化的体验落地。
#
# 锁住 3 件事:
# 1. 空 outcome + 用户选 ready → 后端强制 pending (前端没法绕过质量门)
# 2. 空 outcome + 用户选 pending → 仍 pending (用户明确选暂存)
# 3. 空 outcome + 用户选 needs_data → 后端强制 pending (不是 needs_data)
# 4. 短 outcome (1-9 字符) + 用户选 ready → 仍走 needs_data (现有降级路径)
# 5. task 状态仍正确改成 已完成 (草稿跟"完成"动作不冲突)


@pytest.mark.asyncio
async def test_api_complete_task_empty_outcome_forces_pending(client: TestClient):
    """outcome 完全空 → 即使前端选 ready, 后端强制 cv_status=pending。

    设计意图 (AI_CTO §2.4 + lesson #14): "完成即沉淀" 不能被绕过, 但
    用户当下如果只想"打勾"不该被强制卡。outcome 空 = 用户选了"暂存",
    系统尊重, 但 achievement 不会进报告/CV 直到补全。
    """
    p = await storage.add_project(ProjectCreate(name="P_draft"))
    t = await storage.add_task(TaskCreate(project=p.id, title="快速完成 X"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "",   # ← 完全空
            "cv": f"完成「{t.title}」",
            "cv_status": "ready",  # ← 前端尝试选 ready
            "confirmed_cv": True,  # ← 也尝试声明已确认
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # 关键: outcome 空 → 后端强制 pending, 不让前端绕过
    assert body["cv_status"] == "pending", (
        f"outcome 空 + 前端选 ready 必须被后端强制降级到 pending, "
        f"实际: {body['cv_status']!r} — 质量门失效"
    )
    # task 仍标记已完成 (草稿不阻塞"完成"动作本身)
    task_after = client.get(f"/api/tasks/{t.id}").json()
    assert task_after["status"] == "已完成", (
        "outcome 为空时 task 仍应正确改 status=已完成 (草稿不影响完成动作)"
    )


@pytest.mark.asyncio
async def test_api_complete_task_empty_outcome_with_explicit_pending(client: TestClient):
    """outcome 空 + 用户明确选 pending → 仍 pending (不变)。"""
    p = await storage.add_project(ProjectCreate(name="P_explicit"))
    t = await storage.add_task(TaskCreate(project=p.id, title="Y"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "",
            "cv": f"完成「{t.title}」",
            "cv_status": "pending",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "pending"


@pytest.mark.asyncio
async def test_api_complete_task_empty_outcome_cannot_be_needs_data(client: TestClient):
    """outcome 空 + 前端选 needs_data → 强制 pending (不是 needs_data)。

    理由: needs_data 是"已写 cv 但还差数据"的中间态, outcome 都空就谈不上
    "已写", 走 pending 更准确, 也不会让用户在 /report 看到一堆"差数据"
    但其实根本没写的空条目。
    """
    p = await storage.add_project(ProjectCreate(name="P_no_needs_data"))
    t = await storage.add_task(TaskCreate(project=p.id, title="Z"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "",
            "cv": f"完成「{t.title}」",
            "cv_status": "needs_data",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "pending", (
        f"outcome 空不应被记成 needs_data, 实际: {res.json()['cv_status']!r}"
    )


@pytest.mark.asyncio
async def test_api_complete_task_short_outcome_still_needs_data(client: TestClient):
    """outcome 1-9 字符 (非空) + cv 是 title 兜底 + 前端选 ready → needs_data。

    保留现有降级逻辑: outcome 太短 + cv 没改 → 走 needs_data, 给用户提示
    "你写了点东西, 但 cv 还是任务标题兜底, 需要润色或手填"。
    这跟 outcome 完全空 走 pending 是不同信号, 不能合并。
    """
    p = await storage.add_project(ProjectCreate(name="P_short"))
    t = await storage.add_task(TaskCreate(project=p.id, title="A"))

    res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "修了一下",  # 4 字, 非空
            "cv": f"完成「{t.title}」",  # title 兜底
            "cv_status": "ready",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["cv_status"] == "needs_data", (
        f"outcome 短 + cv 兜底应降级 needs_data, "
        f"实际: {res.json()['cv_status']!r}"
    )

"""API 端点测试 — answerFollowUps + 端到端 cv_status 流转（2026-08-02 v0.3.3 立）。

锁住 v0.3.3 验证标准的 4 个真实缺口:
1. PATCH /api/achievements/{aid}/follow_ups 补全后 cv_status 升级 ready
2. /api/reminders/pending 跟 answerFollowUps 端到端联动（补完后从列表移除）
3. 404 路径（不存在的 aid）
4. answers 字典空 / key 字符串化 / pending 跨级升级 等 edge case

相关 lessons:
- lesson #14（4 字段摩擦 → 1 必填）— follow_ups 是补全路径
- lesson #15（动作≠价值）— follow_up_questions 是 LLM 主动追问
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
async def test_answer_follow_ups_keeps_needs_data_until_final_cv_is_resolved(client: TestClient):
    """补答案只保存证据，旧 CV 不能直接升级 ready。"""
    p = await storage.add_project(ProjectCreate(name="测试项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="完成 PRD"))

    # 任务完成时: needs_data + 有 follow_up_questions
    complete_res = client.post(
        f"/api/tasks/{t.id}/complete",
        json={
            "outcome": "完成了 PRD 撰写",
            "cv": "主导 PRD 撰写 (具体业务指标待补)",
            "cv_status": "needs_data",
            "follow_up_questions": ["具体提升了 DAU 多少?", "影响了哪几个核心模块?"],
        },
    )
    assert complete_res.status_code == 200, complete_res.text
    aid = complete_res.json()["id"]
    assert complete_res.json()["cv_status"] == "needs_data"
    assert len(complete_res.json()["follow_up_questions"]) == 2

    # 补全追问
    res = client.patch(
        f"/api/achievements/{aid}/follow_ups",
        json={"answers": {"0": "DAU +5%", "1": "登录、首页、设置"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["cv_status"] == "needs_data"
    # 答案写入
    assert body["follow_up_answers"]["0"] == "DAU +5%"
    assert body["follow_up_answers"]["1"] == "登录、首页、设置"


@pytest.mark.asyncio
async def test_answer_follow_ups_404_on_missing_aid(client: TestClient):
    """不存在的 aid 必须返 404, 不静默 200."""
    res = client.patch(
        "/api/achievements/non_existent_id_12345/follow_ups",
        json={"answers": {"0": "x"}},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_answer_follow_ups_empty_answers_keeps_status(client: TestClient):
    """空 answers 调用: 应该成功, 但 cv_status 不升级 (没补全 = 数据还是不充分)."""
    p = await storage.add_project(ProjectCreate(name="项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="任务"))
    complete_res = client.post(f"/api/tasks/{t.id}/complete", json={
        "outcome": "o", "cv": "cv 待补", "cv_status": "needs_data",
        "follow_up_questions": ["补全问题?"],
    })
    aid = complete_res.json()["id"]

    res = client.patch(
        f"/api/achievements/{aid}/follow_ups",
        json={"answers": {}},  # 空字典
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # 没补全 = cv_status 应保持 needs_data (后端不应盲升级)
    assert body["cv_status"] == "needs_data"
    assert body["follow_up_answers"] == {}


@pytest.mark.asyncio
async def test_answer_follow_ups_keeps_explicit_draft_pending(client: TestClient):
    """显式草稿补答案后仍是草稿，必须提交新版 CV 才能 resolve。"""
    p = await storage.add_project(ProjectCreate(name="项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="任务"))
    complete_res = client.post(f"/api/tasks/{t.id}/complete", json={
        "outcome": "o", "cv": "cv 草稿", "cv_status": "pending",
        "follow_up_questions": ["补?"],
    })
    aid = complete_res.json()["id"]
    assert complete_res.json()["cv_status"] == "pending"

    res = client.patch(
        f"/api/achievements/{aid}/follow_ups",
        json={"answers": {"0": "补好了"}},
    )
    assert res.status_code == 200
    assert res.json()["cv_status"] == "pending"


@pytest.mark.asyncio
async def test_reminders_pending_and_answer_end_to_end(client: TestClient):
    """端到端: needs_data 出现在 reminders, 补完后从列表移除.

    这是 v0.3.2 智能追问补全闭环的"骨架"链路, 验证 reminders ↔ answer 是真闭环.
    """
    p = await storage.add_project(ProjectCreate(name="项目 A"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="任务 1"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="任务 2"))

    # t1: needs_data（有追问）→ 应出现在 pending
    client.post(f"/api/tasks/{t1.id}/complete", json={
        "outcome": "完成 X 的上线验证并记录待补充证据", "cv": "完成 X，待补充证据", "cv_status": "needs_data",
        "follow_up_questions": ["补 1?", "补 2?"],
    })
    # t2: ready → 不应出现在 pending
    client.post(f"/api/tasks/{t2.id}/complete", json={
        "outcome": "搞了 Y", "cv": "Y 已完整", "cv_status": "ready",
    })

    # 1. pending 列表: 1 条 (t1)
    res = client.get("/api/reminders/pending")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["cv_status"] == "needs_data"
    aid = body["items"][0]["id"]

    # 2. 补全追问只保存答案，仍留在补证队列
    res = client.patch(f"/api/achievements/{aid}/follow_ups", json={
        "answers": {"0": "答案 1", "1": "答案 2"},
    })
    assert res.status_code == 200
    assert res.json()["cv_status"] == "needs_data"

    # 3. pending 列表: 旧 CV 尚未吸收答案，不能移除
    res = client.get("/api/reminders/pending")
    body = res.json()
    assert body["total"] == 1

    # 4. 显式确认重新生成的 CV 后才移除
    res = client.post(f"/api/achievements/{aid}/resolve", json={
        "answers": {"0": "答案 1", "1": "答案 2"},
        "cv": "完成 X，并补充答案 1 和答案 2",
    })
    assert res.status_code == 200
    assert res.json()["cv_status"] == "ready"
    assert client.get("/api/reminders/pending").json()["total"] == 0


@pytest.mark.asyncio
async def test_answer_follow_ups_stringify_int_keys(client: TestClient):
    """answers 的 key 即使传整数, 后端也必须字符串化 (JSON 规范 + 数据库 schema 要求 string).

    防御: 前端用 String(q_idx) 转, 但 API 边界仍要测 — 别假设前端永远转对.
    """
    p = await storage.add_project(ProjectCreate(name="项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="任务"))
    complete_res = client.post(f"/api/tasks/{t.id}/complete", json={
        "outcome": "o", "cv": "cv", "cv_status": "needs_data",
        "follow_up_questions": ["补?"],
    })
    aid = complete_res.json()["id"]

    # 注: JSON 序列化会自动把 int key 转 string, 但显式测一下, 防 Pydantic 改默认行为
    res = client.patch(
        f"/api/achievements/{aid}/follow_ups",
        json={"answers": {"0": "字符串 key 答案"}},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "0" in body["follow_up_answers"]
    assert body["follow_up_answers"]["0"] == "字符串 key 答案"


@pytest.mark.asyncio
async def test_answer_follow_ups_preserves_cv_text(client: TestClient):
    """补全追问不应覆盖原 cv 文本 (cv 是用户/AI 之前填的, 补全是 follow-up 维度, 不冲突)."""
    p = await storage.add_project(ProjectCreate(name="项目"))
    t = await storage.add_task(TaskCreate(project=p.id, title="任务"))
    original_cv = "主导 App 改版 (具体指标待补)"
    complete_res = client.post(f"/api/tasks/{t.id}/complete", json={
        "outcome": "改版完成",
        "cv": original_cv,
        "cv_status": "needs_data",
        "follow_up_questions": ["提升 DAU 多少?"],
    })
    aid = complete_res.json()["id"]

    res = client.patch(
        f"/api/achievements/{aid}/follow_ups",
        json={"answers": {"0": "DAU +5%"}},
    )
    assert res.status_code == 200
    body = res.json()
    # cv 文本保留 (补全追问不覆盖)
    assert body["cv"] == original_cv
    # 旧 CV 未重写，状态仍待补证据
    assert body["cv_status"] == "needs_data"
    # 答案写入
    assert body["follow_up_answers"]["0"] == "DAU +5%"

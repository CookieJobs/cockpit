"""存储层单元测试。"""
import pytest

from app.core import storage
from app.core.models import (
    AchievementUpdate,
    CVStatus,
    Priority,
    ProjectCreate,
    ProjectUpdate,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
)


# ===== Project =====


@pytest.mark.asyncio
async def test_add_and_get_project(temp_db):
    p = await storage.add_project(ProjectCreate(name="Q3 产品迭代"))
    assert p.id.startswith("proj_")
    assert p.name == "Q3 产品迭代"
    assert p.archived is False

    got = await storage.get_project(p.id)
    assert got is not None
    assert got.name == "Q3 产品迭代"


@pytest.mark.asyncio
async def test_list_projects_excludes_archived(temp_db):
    p1 = await storage.add_project(ProjectCreate(name="active"))
    p2 = await storage.add_project(ProjectCreate(name="archived"))
    await storage.update_project(p2.id, ProjectUpdate(archived=True))

    projects = await storage.list_projects(include_archived=False)
    names = {p.name for p in projects}
    assert "active" in names
    assert "archived" not in names

    all_projects = await storage.list_projects(include_archived=True)
    assert len(all_projects) == 2


@pytest.mark.asyncio
async def test_update_project_partial(temp_db):
    p = await storage.add_project(ProjectCreate(name="old name"))
    updated = await storage.update_project(p.id, ProjectUpdate(name="new name"))
    assert updated is not None
    assert updated.name == "new name"
    assert updated.archived is False


@pytest.mark.asyncio
async def test_delete_project_cascades_tasks(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="task1"))

    ok = await storage.delete_project(p.id)
    assert ok is True

    got = await storage.get_task(t.id)
    assert got is None


@pytest.mark.asyncio
async def test_delete_project_not_found(temp_db):
    ok = await storage.delete_project("proj_nonexistent")
    assert ok is False


# ===== Task =====


@pytest.mark.asyncio
async def test_add_task_requires_existing_project(temp_db):
    with pytest.raises(ValueError, match="not found"):
        await storage.add_task(TaskCreate(project="proj_nonexistent", title="x"))


@pytest.mark.asyncio
async def test_add_task_defaults(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    assert t.draft is False  # 新建任务直接进 todo
    assert t.priority == Priority.P2
    assert t.status == TaskStatus.NOT_STARTED
    assert t.checklist == []


@pytest.mark.asyncio
async def test_checklist_add_toggle_remove(temp_db):
    """checklist 增删改。"""
    from app.core.models import ChecklistItem
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(
        TaskCreate(project=p.id, title="x", checklist=[ChecklistItem(text="a"), ChecklistItem(text="b")])
    )
    assert len(t.checklist) == 2

    # append
    t = await storage.checklist_add(t.id, "c")
    assert t is not None
    assert len(t.checklist) == 3
    assert t.checklist[2].text == "c"
    assert t.checklist[2].done is False

    # toggle
    t = await storage.checklist_toggle(t.id, 0)
    assert t is not None
    assert t.checklist[0].done is True

    # remove
    t = await storage.checklist_remove(t.id, 1)
    assert t is not None
    assert len(t.checklist) == 2
    assert t.checklist[0].text == "a"
    assert t.checklist[1].text == "c"


@pytest.mark.asyncio
async def test_update_task_partial(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    updated = await storage.update_task(
        t.id,
        TaskUpdate(priority=Priority.P0, draft=False),
    )
    assert updated is not None
    assert updated.priority == Priority.P0
    assert updated.draft is False
    # 其他字段不变
    assert updated.title == "x"


@pytest.mark.asyncio
async def test_update_task_not_found(temp_db):
    updated = await storage.update_task("task_xxx", TaskUpdate(title="x"))
    assert updated is None


@pytest.mark.asyncio
async def test_confirm_drafts(temp_db):
    """confirm_all_drafts 把 draft=True 的任务批量改为 draft=False。"""
    p = await storage.add_project(ProjectCreate(name="x"))
    # 默认 draft=False，主动设 draft=True 才能测 confirm
    t1 = await storage.add_task(TaskCreate(project=p.id, title="a"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="b"))
    await storage.update_task(t1.id, TaskUpdate(draft=True))
    await storage.update_task(t2.id, TaskUpdate(draft=True))

    count = await storage.confirm_all_drafts()
    assert count == 2

    g1 = await storage.get_task(t1.id)
    g2 = await storage.get_task(t2.id)
    assert g1.draft is False
    assert g2.draft is False


@pytest.mark.asyncio
async def test_delete_task(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    ok = await storage.delete_task(t.id)
    assert ok is True
    got = await storage.get_task(t.id)
    assert got is None


# ===== Achievement =====


@pytest.mark.asyncio
async def test_complete_task_creates_achievement(temp_db):
    p = await storage.add_project(ProjectCreate(name="Q3 产品迭代"))
    t = await storage.add_task(TaskCreate(project=p.id, title="修登录 bug"))

    achievement = await storage.complete_task(
        t.id,
        outcome="bug 修好了",
        reflection="定位花了 1 小时",
        cv="修复高优先级登录鉴权 bug",
        cv_status=CVStatus.READY,
    )

    assert achievement is not None
    assert achievement.id.startswith("done_")
    assert achievement.project_id == p.id
    assert achievement.project == "Q3 产品迭代"  # 名称快照
    assert achievement.title == "修登录 bug"  # 标题快照
    assert achievement.cv == "修复高优先级登录鉴权 bug"
    assert achievement.cv_status == CVStatus.READY

    # task 已被删
    got = await storage.get_task(t.id)
    assert got is None


@pytest.mark.asyncio
async def test_complete_task_pending_status(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))

    a = await storage.complete_task(
        t.id, outcome="done", cv="做了 X", cv_status=CVStatus.PENDING
    )
    assert a.cv_status == CVStatus.PENDING


@pytest.mark.asyncio
async def test_complete_task_needs_data_status(temp_db):
    """needs_data 中间态（2026-07-20 立）: cv 已写但还差数据。

    跟 pending 区别：pending 是"没写完"，needs_data 是"写了但承认不全"。
    """
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))

    a = await storage.complete_task(
        t.id,
        outcome="搞了 X",
        cv="主导 X 改版上线（具体指标待补）",
        cv_status=CVStatus.NEEDS_DATA,
    )
    assert a.cv_status == CVStatus.NEEDS_DATA
    # cv 文本应保留
    assert "待补" in a.cv


@pytest.mark.asyncio
async def test_list_achievements_filter_by_cv_status(temp_db):
    """list_achievements 的 cv_status 精确过滤（2026-07-20 立）。"""
    p = await storage.add_project(ProjectCreate(name="x"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="t1"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="t2"))
    t3 = await storage.add_task(TaskCreate(project=p.id, title="t3"))
    await storage.complete_task(t1.id, outcome="o", cv="c", cv_status=CVStatus.READY)
    await storage.complete_task(t2.id, outcome="o", cv="c", cv_status=CVStatus.NEEDS_DATA)
    await storage.complete_task(t3.id, outcome="o", cv="c", cv_status=CVStatus.PENDING)

    ready = await storage.list_achievements(cv_status=CVStatus.READY)
    needs = await storage.list_achievements(cv_status=CVStatus.NEEDS_DATA)
    pending = await storage.list_achievements(cv_status=CVStatus.PENDING)

    assert len(ready) == 1
    assert len(needs) == 1
    assert len(pending) == 1
    assert ready[0].cv_status == CVStatus.READY
    assert needs[0].cv_status == CVStatus.NEEDS_DATA
    assert pending[0].cv_status == CVStatus.PENDING


@pytest.mark.asyncio
async def test_needs_data_to_ready_upgrade(temp_db):
    """needs_data → ready 升级路径（典型场景：3 个月后补全数据）。"""
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    a = await storage.complete_task(
        t.id, outcome="o", cv="主导改版", cv_status=CVStatus.NEEDS_DATA
    )
    # 升级
    upgraded = await storage.update_achievement_cv(
        a.id, AchievementUpdate(cv="主导 App 改版，DAU +5%", cv_status=CVStatus.READY)
    )
    assert upgraded.cv == "主导 App 改版，DAU +5%"
    assert upgraded.cv_status == CVStatus.READY


@pytest.mark.asyncio
async def test_complete_task_not_found(temp_db):
    a = await storage.complete_task("task_xxx", outcome="o", cv="cv")
    assert a is None


@pytest.mark.asyncio
async def test_update_achievement_cv(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    a = await storage.complete_task(t.id, outcome="o", cv="old cv", cv_status=CVStatus.PENDING)

    updated = await storage.update_achievement_cv(
        a.id, AchievementUpdate(cv="new cv with metrics", cv_status=CVStatus.READY)
    )
    assert updated.cv == "new cv with metrics"
    assert updated.cv_status == CVStatus.READY


@pytest.mark.asyncio
async def test_undo_completion_restores_task(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t = await storage.add_task(TaskCreate(project=p.id, title="x"))
    a = await storage.complete_task(t.id, outcome="o", cv="cv")

    restored = await storage.undo_completion(a.id)
    assert restored is not None
    assert restored.id == t.id
    assert restored.status == TaskStatus.IN_PROGRESS

    # achievement 已删
    items = await storage.list_achievements()
    assert len(items) == 0


@pytest.mark.asyncio
async def test_undo_completion_not_found(temp_db):
    restored = await storage.undo_completion("done_xxx")
    assert restored is None


@pytest.mark.asyncio
async def test_list_achievements_filter(temp_db):
    p1 = await storage.add_project(ProjectCreate(name="P1"))
    p2 = await storage.add_project(ProjectCreate(name="P2"))

    t1 = await storage.add_task(TaskCreate(project=p1.id, title="t1"))
    t2 = await storage.add_task(TaskCreate(project=p2.id, title="t2"))

    a1 = await storage.complete_task(t1.id, outcome="o1", cv="cv1", cv_status=CVStatus.READY)
    a2 = await storage.complete_task(t2.id, outcome="o2", cv="cv2", cv_status=CVStatus.PENDING)

    # 按项目名过滤
    items = await storage.list_achievements(project_name="P1")
    assert len(items) == 1
    assert items[0].id == a1.id

    # 只看 ready
    items = await storage.list_achievements(only_ready=True)
    assert len(items) == 1

    # 不过滤
    items = await storage.list_achievements()
    assert len(items) == 2


# ===== Snapshot =====


@pytest.mark.asyncio
async def test_build_snapshot_focus_ordering(temp_db):
    """focus 排序：blocked 后排 + priority 升序。"""
    p = await storage.add_project(ProjectCreate(name="x"))

    t_high = await storage.add_task(TaskCreate(project=p.id, title="high", priority=Priority.P0))
    t_medium = await storage.add_task(TaskCreate(project=p.id, title="medium", priority=Priority.P2))
    t_blocked = await storage.add_task(
        TaskCreate(project=p.id, title="blocked", priority=Priority.P0, blocked=True)
    )

    snapshot = await storage.build_snapshot()
    assert len(snapshot.focus) == 3
    assert snapshot.focus[0].title == "high"
    assert snapshot.focus[1].title == "medium"
    assert snapshot.focus[2].title == "blocked"


@pytest.mark.asyncio
async def test_build_snapshot_excludes_drafts(temp_db):
    """draft=True 的任务不进 focus。"""
    p = await storage.add_project(ProjectCreate(name="x"))

    # 默认 draft=False 的会进 focus
    await storage.add_task(TaskCreate(project=p.id, title="todo"))
    # 主动设 draft=True 才不进 focus
    t_draft = await storage.add_task(TaskCreate(project=p.id, title="draft"))
    await storage.update_task(t_draft.id, TaskUpdate(draft=True))

    snapshot = await storage.build_snapshot()
    titles = [f.title for f in snapshot.focus]
    assert "todo" in titles
    assert "draft" not in titles


@pytest.mark.asyncio
async def test_build_snapshot_counts(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="t1"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="t2"))

    await storage.complete_task(t1.id, outcome="o", cv="cv1", cv_status=CVStatus.READY)
    await storage.complete_task(t2.id, outcome="o", cv="cv2", cv_status=CVStatus.PENDING)

    snapshot = await storage.build_snapshot()
    assert snapshot.counts["achievementsReady"] == 1
    assert snapshot.counts["achievementsPending"] == 1


@pytest.mark.asyncio
async def test_build_snapshot_groups_by_project(temp_db):
    p1 = await storage.add_project(ProjectCreate(name="P1"))
    p2 = await storage.add_project(ProjectCreate(name="P2"))

    await storage.add_task(TaskCreate(project=p1.id, title="p1-task1"))
    await storage.add_task(TaskCreate(project=p2.id, title="p2-task1"))

    snapshot = await storage.build_snapshot()
    project_names = [ps.name for ps in snapshot.projects]
    assert "P1" in project_names
    assert "P2" in project_names


@pytest.mark.asyncio
async def test_build_snapshot_includes_project_description(temp_db):
    """build_snapshot 必须把 project.description 带出来,否则前端看板永远看不到。

    历史 bug: storage.py:927 漏传 description 字段,前端 ProjectSnapshot 类型又是
    optional,导致 description 有值也显示空白,UI 完全感知不到该字段存在。
    """
    p_with_desc = await storage.add_project(
        ProjectCreate(name="有描述", description="提升产品中的AI含量及token消耗量")
    )
    p_empty_desc = await storage.add_project(ProjectCreate(name="无描述"))
    await storage.add_task(TaskCreate(project=p_with_desc.id, title="t"))

    snapshot = await storage.build_snapshot()

    by_id = {ps.id: ps for ps in snapshot.projects}
    assert by_id[p_with_desc.id].description == "提升产品中的AI含量及token消耗量"
    assert by_id[p_empty_desc.id].description == ""
    # 未分组的 project id=None 也得能跑通（不崩,空字符串）
    orphan_groups = [ps for ps in snapshot.projects if ps.id is None]
    if orphan_groups:
        assert orphan_groups[0].description == ""


# ===== Priority 迁移 (2026-07-22 立) =====


@pytest.mark.asyncio
async def test_migrate_priority_old_to_new(temp_db):
    """启动时一次性把旧 priority 值 (高/中/低) 映射到新值 (P0/P2/P3)。

    历史背景: Priority enum 从 3 档 (高/中/低) 升级到 4 档 (P0/P1/P2/P3),
    旧 DB 数据加载会 ValidationError。create_tables() 启动时跑 UPDATE 兼容老数据。

    映射规则:
    - 高 → P0 (紧急)
    - 中 → P2 (普通, 默认档)
    - 低 → P3 (不急)
    - P1 是新档, 旧数据没有对应 — 用户后续手动调整
    """
    from sqlalchemy import text

    p = await storage.add_project(ProjectCreate(name="legacy"))
    t_high = await storage.add_task(TaskCreate(project=p.id, title="urgent"))
    t_med = await storage.add_task(TaskCreate(project=p.id, title="normal"))
    t_low = await storage.add_task(TaskCreate(project=p.id, title="later"))

    # 手动把 priority 写回旧值, 模拟升级前已存在的 DB 数据
    from app.core.storage import _engine
    async with _engine.begin() as conn:  # type: ignore[union-attr]
        await conn.execute(
            text("UPDATE tasks SET priority = :v WHERE id = :id"),
            {"v": "高", "id": t_high.id},
        )
        await conn.execute(
            text("UPDATE tasks SET priority = :v WHERE id = :id"),
            {"v": "中", "id": t_med.id},
        )
        await conn.execute(
            text("UPDATE tasks SET priority = :v WHERE id = :id"),
            {"v": "低", "id": t_low.id},
        )

    # 跑一次 create_tables() 触发 migration (idempotent — 重复跑不重复更新)
    await storage.create_tables()
    await storage.create_tables()  # 第二次: 应该 no-op

    # 读回, 验证旧值已被映射
    by_id = {t.id: t for t in await storage.list_tasks()}
    assert by_id[t_high.id].priority == Priority.P0
    assert by_id[t_med.id].priority == Priority.P2
    assert by_id[t_low.id].priority == Priority.P3

    # 新值不会被"再次" 映射 (再次跑也是 no-op)
    await storage.create_tables()
    by_id2 = {t.id: t for t in await storage.list_tasks()}
    assert by_id2[t_high.id].priority == Priority.P0
    assert by_id2[t_med.id].priority == Priority.P2
    assert by_id2[t_low.id].priority == Priority.P3

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
    assert t.draft is True
    assert t.priority == Priority.MEDIUM
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
        TaskUpdate(priority=Priority.HIGH, draft=False),
    )
    assert updated is not None
    assert updated.priority == Priority.HIGH
    assert updated.draft is False
    # 其他字段不变
    assert updated.title == "x"


@pytest.mark.asyncio
async def test_update_task_not_found(temp_db):
    updated = await storage.update_task("task_xxx", TaskUpdate(title="x"))
    assert updated is None


@pytest.mark.asyncio
async def test_confirm_drafts(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))
    t1 = await storage.add_task(TaskCreate(project=p.id, title="a"))
    t2 = await storage.add_task(TaskCreate(project=p.id, title="b"))

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

    t_high = await storage.add_task(TaskCreate(project=p.id, title="high", priority=Priority.HIGH))
    await storage.update_task(t_high.id, TaskUpdate(draft=False))

    t_medium = await storage.add_task(TaskCreate(project=p.id, title="medium", priority=Priority.MEDIUM))
    await storage.update_task(t_medium.id, TaskUpdate(draft=False))

    t_blocked = await storage.add_task(
        TaskCreate(project=p.id, title="blocked", priority=Priority.HIGH, blocked=True)
    )
    await storage.update_task(t_blocked.id, TaskUpdate(draft=False))

    snapshot = await storage.build_snapshot()
    assert len(snapshot.focus) == 3
    assert snapshot.focus[0].title == "high"
    assert snapshot.focus[1].title == "medium"
    assert snapshot.focus[2].title == "blocked"


@pytest.mark.asyncio
async def test_build_snapshot_excludes_drafts(temp_db):
    p = await storage.add_project(ProjectCreate(name="x"))

    # 默认 draft
    await storage.add_task(TaskCreate(project=p.id, title="draft"))
    t_confirmed = await storage.add_task(TaskCreate(project=p.id, title="confirmed"))
    await storage.update_task(t_confirmed.id, TaskUpdate(draft=False))

    snapshot = await storage.build_snapshot()
    titles = [f.title for f in snapshot.focus]
    assert "draft" not in titles
    assert "confirmed" in titles


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

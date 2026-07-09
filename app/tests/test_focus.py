"""Focus 排序单元测试。"""
from datetime import date

from app.core.focus import sort_focus, take_focus
from app.core.models import Priority, Task, TaskStatus


def _make_task(id: str, **kwargs) -> Task:
    defaults = dict(
        id=id, project="proj_1", title=f"task-{id}",
        status=TaskStatus.NOT_STARTED, priority=Priority.MEDIUM,
        due=None, next_action="", blocked=False, draft=False, created_at=date.today(),
        completed_at=None, checklist=[],
    )
    defaults.update(kwargs)
    return Task(**defaults)


def test_sort_focus_priority():
    """优先级排序：高 > 中 > 低。"""
    tasks = [
        _make_task("low", priority=Priority.LOW),
        _make_task("high", priority=Priority.HIGH),
        _make_task("medium", priority=Priority.MEDIUM),
    ]
    sorted_tasks = sort_focus(tasks)
    assert [t.id for t in sorted_tasks] == ["high", "medium", "low"]


def test_sort_focus_excludes_drafts():
    """草稿不进 focus。"""
    tasks = [
        _make_task("a", draft=True),
        _make_task("b", draft=False),
    ]
    sorted_tasks = sort_focus(tasks)
    assert [t.id for t in sorted_tasks] == ["b"]


def test_sort_focus_blocked_last():
    """blocked 排在非 blocked 后面（即使 priority 更高）。"""
    tasks = [
        _make_task("blocked-high", priority=Priority.HIGH, blocked=True),
        _make_task("normal-medium", priority=Priority.MEDIUM, blocked=False),
    ]
    sorted_tasks = sort_focus(tasks)
    assert sorted_tasks[0].id == "normal-medium"
    assert sorted_tasks[1].id == "blocked-high"


def test_sort_focus_due_order():
    """有 due 任务排在无 due 之前；due 早的排前。"""
    tasks = [
        _make_task("no-due"),
        _make_task("due-later", due=date(2026, 12, 31)),
        _make_task("due-soon", due=date(2026, 7, 1)),
    ]
    sorted_tasks = sort_focus(tasks)
    assert [t.id for t in sorted_tasks] == ["due-soon", "due-later", "no-due"]


def test_take_focus_limit():
    """take_focus 取 Top N。"""
    tasks = [_make_task(f"t{i}", priority=Priority.MEDIUM) for i in range(10)]
    focus = take_focus(tasks, limit=3)
    assert len(focus) == 3


def test_take_focus_default_limit_5():
    """take_focus 默认 limit=5。"""
    tasks = [_make_task(f"t{i}") for i in range(10)]
    focus = take_focus(tasks)
    assert len(focus) == 5

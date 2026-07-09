"""数据模型单元测试。"""
import pytest
from pydantic import ValidationError

from app.core.models import (
    Achievement,
    CVStatus,
    Priority,
    Project,
    ProjectCreate,
    Task,
    TaskCreate,
    TaskStatus,
)


def test_project_id_format():
    """项目 ID 应以 proj_ 开头。"""
    p = Project(name="test")
    assert p.id.startswith("proj_")
    assert len(p.id) > len("proj_")


def test_project_id_unique():
    """连续生成的项目 ID 应唯一。"""
    ids = {Project(name=str(i)).id for i in range(100)}
    assert len(ids) == 100


def test_project_name_required():
    """项目名不能为空。"""
    with pytest.raises(ValidationError):
        ProjectCreate(name="")
    with pytest.raises(ValidationError):
        ProjectCreate()  # type: ignore[call-arg]


def test_priority_enum_values():
    """优先级合法值。"""
    assert Priority.HIGH.value == "高"
    assert Priority.MEDIUM.value == "中"
    assert Priority.LOW.value == "低"


def test_task_create_requires_project():
    """任务必须有 project。"""
    with pytest.raises(ValidationError):
        TaskCreate(title="x")  # type: ignore[call-arg]


def test_task_default_draft_true():
    """新任务默认 draft=True。"""
    t = Task(project="proj_xxx", title="x")
    assert t.draft is True
    assert t.status == TaskStatus.NOT_STARTED
    assert t.priority == Priority.MEDIUM
    assert t.blocked is False
    assert t.checklist == []


def test_task_checklist_default():
    """checklist 默认空列表。"""
    t = Task(project="proj_xxx", title="x", checklist=[])
    assert t.checklist == []


def test_task_checklist_with_items():
    """checklist 接受 ChecklistItem 列表。"""
    from app.core.models import ChecklistItem
    items = [ChecklistItem(text="a", done=False), ChecklistItem(text="b", done=True)]
    t = Task(project="proj_xxx", title="x", checklist=items)
    assert len(t.checklist) == 2
    assert t.checklist[0].text == "a"
    assert t.checklist[1].done is True


def test_checklist_item_default_done_false():
    """ChecklistItem 默认 done=False。"""
    from app.core.models import ChecklistItem
    item = ChecklistItem(text="buy milk")
    assert item.text == "buy milk"
    assert item.done is False


def test_achievement_cv_status_default():
    """成就默认 cv_status=ready。"""
    a = Achievement(task_id="task_xxx", project_id="proj_xxx", project="test", title="x")
    assert a.cv_status == CVStatus.READY
    assert a.date is not None
    assert a.outcome == ""
    assert a.reflection == ""


def test_achievement_id_format():
    """成就 ID 应以 done_ 开头。"""
    a = Achievement(task_id="task_xxx", project_id="proj_xxx", project="p", title="t")
    assert a.id.startswith("done_")

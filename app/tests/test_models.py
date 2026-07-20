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


def test_task_default_draft_false():
    """新任务默认 draft=False（直接进 todo，无需确认）。"""
    t = Task(project="proj_xxx", title="x")
    assert t.draft is False
    assert t.status == TaskStatus.NOT_STARTED
    assert t.priority == Priority.MEDIUM
    assert t.blocked is False
    assert t.checklist == []
    assert t.description == ""


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


def test_cv_status_enum_has_three_states():
    """CVStatus 三态（2026-07-20 立 needs_data 中间态）。"""
    assert CVStatus.READY.value == "ready"
    assert CVStatus.NEEDS_DATA.value == "needs_data"
    assert CVStatus.PENDING.value == "pending"
    assert len(CVStatus) == 3


def test_achievement_id_format():
    """成就 ID 应以 done_ 开头。"""
    a = Achievement(task_id="task_xxx", project_id="proj_xxx", project="p", title="t")
    assert a.id.startswith("done_")


def test_project_description_default():
    """Project.description 默认空串。"""
    from app.core.models import Project
    p = Project(name="x")
    assert p.description == ""
    p2 = Project(name="x", description="负责 Q4 增长")
    assert p2.description == "负责 Q4 增长"


def test_task_description_default():
    """Task.description 默认空串，可设置。"""
    from app.core.models import Task
    t = Task(project="proj_x", title="x", description="需要重构数据库 schema")
    assert t.description == "需要重构数据库 schema"


def test_project_update_allows_description():
    """ProjectUpdate.description 可选。"""
    from app.core.models import ProjectUpdate
    u = ProjectUpdate(description="新描述")
    assert u.description == "新描述"
    u2 = ProjectUpdate(name="新名")
    assert u2.description is None


def test_task_update_allows_description():
    """TaskUpdate.description 可选。"""
    from app.core.models import TaskUpdate
    u = TaskUpdate(description="新详情")
    assert u.description == "新详情"

"""拾光数据模型（pydantic v2）。

设计哲学（继承自 task-cockpit skill）：
- 三个核心实体：Project / Task / Achievement
- 字符串 ID（proj_xxx / task_xxx / done_xxx）方便跨平台数据迁移
- Achievement append-only，只 update cv/cvStatus
- cvStatus 状态机：pending → ready（数据补充标记）
- 任务完成后必沉淀为 Achievement

注意：pydantic 2.13 + Python 3.14 下，字段名与类型同名（如 date: date）
会导致 "field name clashing with a type annotation" 错误。规避方案：
用 `Annotated[T, Field(default_factory=...)]` 而非 `T = Field(default_factory=...)`。
"""
import time
import uuid
from datetime import date
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _today() -> date:
    """返回今天的 date 对象（用于 default_factory）。"""
    return date.today()


def _new_id(prefix: str) -> str:
    """生成 skill 兼容的 ID 格式：{prefix}_{13位时间戳}{6位uuid}。

    与 task-cockpit skill 完全相同的格式，便于跨平台数据迁移。
    """
    return f"{prefix}_{int(time.time() * 1000):013d}{uuid.uuid4().hex[:6]}"


# 类型别名：date 字段（解决 pydantic 2.13 + Python 3.14 字段名/类型同名问题）
DateField = Annotated[date, Field(default_factory=_today)]


# ===== Enums =====


class Priority(str, Enum):
    """任务优先级。"""
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class TaskStatus(str, Enum):
    """任务状态。"""
    NOT_STARTED = "未开始"
    IN_PROGRESS = "进行中"
    COMPLETED = "已完成"


class CVStatus(str, Enum):
    """成就的 CV 状态。"""
    PENDING = "pending"   # 数据模糊、待补充
    READY = "ready"       # 数据充分、可用


# ===== Checklist =====


# 注意：ChecklistItem 在 ShiguangModel 之前定义，因此先用一个最小类
# 然后等 ShiguangModel 定义后再升级
class _ChecklistItemPending:
    """占位，定义后会被覆盖。"""
    pass


# ===== Base =====


class ShiguangModel(BaseModel):
    """拾光模型基类。"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


class ChecklistItem(ShiguangModel):
    """任务子项（清单项）。"""
    text: str = Field(..., min_length=1, max_length=500)
    done: bool = False


# ===== Project =====


class ProjectBase(ShiguangModel):
    name: str = Field(..., min_length=1, max_length=200)


class ProjectCreate(ProjectBase):
    """创建项目的入参。"""
    pass


class ProjectUpdate(ShiguangModel):
    """更新项目的入参。"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    archived: Optional[bool] = None


class Project(ProjectBase):
    """项目实体。"""
    id: str = Field(default_factory=lambda: _new_id("proj"))
    created_at: DateField
    archived: bool = Field(default=False)


# ===== Task =====


class TaskBase(ShiguangModel):
    title: str = Field(..., min_length=1, max_length=500)
    priority: Priority = Field(default=Priority.MEDIUM)
    due: Optional[date] = None
    next_action: str = Field(default="", max_length=500)
    blocked: bool = False
    checklist: List[ChecklistItem] = Field(default_factory=list)


class TaskCreate(TaskBase):
    """创建任务的入参。"""
    project: str = Field(..., description="项目 ID")


class TaskUpdate(ShiguangModel):
    """更新任务的入参（部分字段可选）。"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    due: Optional[date] = None
    next_action: Optional[str] = Field(None, max_length=500)
    blocked: Optional[bool] = None
    draft: Optional[bool] = None
    checklist: Optional[list[str]] = None


class Task(TaskBase):
    """任务实体。"""
    id: str = Field(default_factory=lambda: _new_id("task"))
    project: str = Field(..., description="项目 ID")
    status: TaskStatus = Field(default=TaskStatus.NOT_STARTED)
    draft: bool = Field(default=True, description="待用户确认")
    created_at: DateField
    completed_at: Optional[date] = None


# ===== Achievement =====


class AchievementBase(ShiguangModel):
    outcome: str = Field(default="", description="用户描述的结果")
    reflection: str = Field(default="", description="用户复盘")
    cv: str = Field(default="", description="agent 生成的 CV 描述")
    cv_status: CVStatus = Field(default=CVStatus.READY)


class AchievementCreate(AchievementBase):
    """创建成就的入参。"""
    task_id: str


class AchievementUpdate(ShiguangModel):
    """更新成就的入参（只允许更新 cv 相关字段，符合 append-only 原则）。"""
    cv: Optional[str] = None
    cv_status: Optional[CVStatus] = None


class Achievement(AchievementBase):
    """成就实体（append-only 记录）。"""
    id: str = Field(default_factory=lambda: _new_id("done"))
    date: DateField
    task_id: str
    project_id: str
    project: str = Field(..., description="项目名称快照")
    title: str = Field(..., description="任务标题快照")
    tags: List[str] = Field(default_factory=list)


# ===== Snapshot（用于 dashboard / 问局势）=====


class FocusItem(ShiguangModel):
    """今日聚焦条目。"""
    id: str
    project: str
    title: str
    priority: Priority
    due: Optional[date] = None
    blocked: bool
    next_action: str = ""


class ProjectSnapshot(ShiguangModel):
    """项目快照（含任务）。"""
    id: Optional[str]
    name: str
    tasks: list[Task]


class Snapshot(ShiguangModel):
    """全局快照。"""
    focus: list[FocusItem]
    projects: list[ProjectSnapshot]
    done_today: list[Achievement]
    counts: dict[str, int]

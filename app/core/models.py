"""Cockpit数据模型（pydantic v2）。

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
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, List, Optional

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


# 注意：ChecklistItem 在 CockpitModel 之前定义，因此先用一个最小类
# 然后等 CockpitModel 定义后再升级
class _ChecklistItemPending:
    """占位，定义后会被覆盖。"""
    pass


# ===== Base =====


class CockpitModel(BaseModel):
    """Cockpit模型基类。"""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


class ChecklistItem(CockpitModel):
    """任务子项（清单项）。"""
    text: str = Field(..., min_length=1, max_length=500)
    done: bool = False


# ===== LLM Settings（用户在 UI 配）=====


class LLMBackend(str, Enum):
    """LLM 后端类型。

    设计原则：覆盖国内主流云厂商，用户只需输入 API Key 即可使用。
    """
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"  # DeepSeek 官方 API
    MINIMAX = "minimax"   # MiniMax（默认走 OpenAI 兼容端点）
    OPENAI = "openai"      # OpenAI 官方 / 其他 OpenAI 兼容
    CUSTOM = "custom"


# 各后端的推荐模型预设（按用户基数和实用性排）
LLM_MODEL_PRESETS: dict[str, list[str]] = {
    "anthropic": [
        "claude-sonnet-4-5",
        "claude-opus-4-5",
        "claude-3-5-haiku-20241022",
    ],
    "deepseek": [
        # DeepSeek 官方 OpenAI 兼容 API (https://api.deepseek.com/v1) 用的模型名
        # 注：旧名 deepseek-chat / deepseek-reasoner 在 2026-07-24 停用，请切到 V4
        "deepseek-v4-flash",      # 2026-04 快速模式：284B / 13B 激活 / 1M 上下文
        "deepseek-v4-pro",        # 2026-04 专家模式：1.6T / 49B 激活 / 1M 上下文
    ],
    "minimax": [
        # MiniMax 官方 OpenAI 兼容 API (https://api.minimaxi.com/v1) 用的模型名
        # 见 https://platform.minimaxi.com/
        "MiniMax-M3",     # 2026-06 旗舰：1M 上下文 / Coding & Agent / 原生多模态
        "MiniMax-M2.7",   # 2026-04 开源：自我进化 + 可视化交互
        "MiniMax-M2",     # 2025-10 开源：230B MoE / 编码 & Agent 强
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "moonshot-v1-128k",
    ],
    "custom": [],  # 用户自由输入
}


class LLMSettings(CockpitModel):
    """用户在 UI 配的 LLM 配置（运行时）。

    优先级：DB（用户配）> .env（部署配）> 默认
    """
    backend: LLMBackend
    model: str = Field(..., min_length=1)
    api_key: Optional[str] = Field(None, description="API key（明文存储，单人本地工具暂不加密）")
    base_url: Optional[str] = Field(None, description="自定义 endpoint URL")


class LLMSettingsPublic(CockpitModel):
    """LLM 设置（脱敏响应：key 只显示前 4 + 后 4 位）"""
    backend: LLMBackend
    model: str
    api_key_masked: Optional[str] = None
    base_url: Optional[str] = None
    has_key: bool = False
    source: str = "env"  # "db" | "env" | "default"


class LLMSettingsUpdate(CockpitModel):
    """更新 LLM 设置的入参（所有字段可选）。"""
    backend: Optional[LLMBackend] = None
    model: Optional[str] = Field(None, min_length=1)
    api_key: Optional[str] = None
    base_url: Optional[str] = None


def mask_key(key: Optional[str]) -> Optional[str]:
    """脱敏 API key：前 4 + ... + 后 4。"""
    if not key:
        return None
    if len(key) <= 12:
        return key[:2] + "***" + key[-2:]
    return key[:4] + "..." + key[-4:]


# ===== Project =====


class ProjectBase(CockpitModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000, description="项目描述 / 目标")


class ProjectCreate(ProjectBase):
    """创建项目的入参。"""
    pass


class ProjectUpdate(CockpitModel):
    """更新项目的入参。"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    archived: Optional[bool] = None


class Project(ProjectBase):
    """项目实体。"""
    id: str = Field(default_factory=lambda: _new_id("proj"))
    created_at: DateField
    archived: bool = Field(default=False)


# ===== Task =====


class TaskBase(CockpitModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000, description="任务详情 / 上下文")
    priority: Priority = Field(default=Priority.MEDIUM)
    due: Optional[date] = None
    next_action: str = Field(default="", max_length=500)
    blocked: bool = False
    checklist: List[ChecklistItem] = Field(default_factory=list)


class TaskCreate(TaskBase):
    """创建任务的入参。"""
    project: str = Field(..., description="项目 ID")


class TaskUpdate(CockpitModel):
    """更新任务的入参（部分字段可选）。"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
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
    draft: bool = Field(default=False, description="待用户确认（默认 False，新任务直接进 todo）")
    created_at: DateField
    completed_at: Optional[date] = None


# ===== Achievement =====


class AchievementBase(CockpitModel):
    outcome: str = Field(default="", description="用户描述的结果")
    reflection: str = Field(default="", description="用户复盘")
    cv: str = Field(default="", description="agent 生成的 CV 描述")
    cv_status: CVStatus = Field(default=CVStatus.READY)


class AchievementCreate(AchievementBase):
    """创建成就的入参。"""
    task_id: str


class AchievementUpdate(CockpitModel):
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


class FocusItem(CockpitModel):
    """今日聚焦条目。"""
    id: str
    project: str
    title: str
    priority: Priority
    due: Optional[date] = None
    blocked: bool
    next_action: str = ""


class ProjectSnapshot(CockpitModel):
    """项目快照（含任务）。"""
    id: Optional[str]
    name: str
    tasks: list[Task]


class Snapshot(CockpitModel):
    """全局快照。"""
    focus: list[FocusItem]
    projects: list[ProjectSnapshot]
    done_today: list[Achievement]
    counts: dict[str, int]


# ===== Chat Sessions =====


class ChatSession(CockpitModel):
    """对话 session。

    Session 隔离策略：
    - id 由前端生成（UUID），存 localStorage
    - 跨刷新保留；切换浏览器/隐身模式自动建新 session
    - 后端不区分设备，只按 session_id 存
    """
    id: str
    label: str = Field(default="新对话")
    created_at: datetime
    last_active_at: datetime
    archived: bool = Field(default=False)
    message_count: int = Field(default=0)


class ChatMessage(CockpitModel):
    """单条对话消息。

    存盘用 Anthropic 格式的 content list（支持 tool_use/tool_result blocks），
    LLM 客户端会自己转换。role 取值：
    - "user"：用户输入，或 assistant 调工具后的 tool_result 合并消息
    - "assistant"：LLM 回复（含 tool_use blocks）
    """
    id: str
    session_id: str
    role: str  # "user" | "assistant"
    content: str  # 序列化的 Anthropic content list（JSON 字符串）
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        default=None, description="assistant 消息的工具调用摘要（用于 UI 展示）"
    )
    created_at: datetime

"""拾光 Focus 排序逻辑。

继承自 task-cockpit skill 的排序规则：
1. draft 任务不进入 focus
2. blocked 任务排在非 blocked 后面
3. priority rank 升序（高=0, 中=1, 低=2）
4. due 升序，无 due 用 "9999-99-99" 占位
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models import Task


_PRIORITY_RANK = {"高": 0, "中": 1, "低": 2}


def _focus_key(task: "Task") -> tuple[int, int, str]:
    """生成 focus 排序 key。"""
    blocked_rank = 1 if task.blocked else 0
    # 支持 pydantic enum 和字符串
    priority_value = task.priority.value if hasattr(task.priority, "value") else task.priority
    priority_rank = _PRIORITY_RANK.get(priority_value, 1)
    due = task.due.isoformat() if task.due else "9999-99-99"
    return (blocked_rank, priority_rank, due)


def sort_focus(tasks: list["Task"]) -> list["Task"]:
    """按 focus 规则排序任务列表（draft 排除）。"""
    non_draft = [t for t in tasks if not t.draft]
    return sorted(non_draft, key=_focus_key)


def take_focus(tasks: list["Task"], limit: int = 5) -> list["Task"]:
    """取 Top N focus 任务。"""
    return sort_focus(tasks)[:limit]

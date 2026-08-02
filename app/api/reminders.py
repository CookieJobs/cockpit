"""补全追问提醒端点 (2026-08-01 立)。

扫描 cv_status != ready 且有 follow_up_questions 的成就, 返 Achievement 列表。
前端用 Achievement.follow_up_questions / follow_up_answers 直接渲染, 不用新建类型。

格式跟 /api/achievements 一致 (返 Achievement), 多个 total 字段标总待补数。
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import storage
from app.core.models import Achievement, CVStatus

router = APIRouter()


class RemindersResponse(BaseModel):
    """补全提醒列表响应 (2026-08-01 立)。

    items: Achievement 列表 (跟 /api/achievements 同 schema, 含 follow_up_questions)
    total: 总待补数 (不限于本页 limit)
    """
    items: list[Achievement]
    total: int


@router.get("/pending", response_model=RemindersResponse)
async def list_pending_follow_ups(
    cv_status: Optional[CVStatus] = None,
    limit: int = 50,
) -> RemindersResponse:
    """扫 cv_status != ready 且有 follow_up_questions 的成就。

    Args:
        cv_status: 可选过滤 (e.g. 只看 needs_data)
        limit: 最多返多少条 (默认 50)

    Returns:
        {items: Achievement[], total: N}
        - items 顺序: 按 date desc (最近完成的在前)
        - total: 过滤后的总待补数 (不含 limit 截断)
    """
    items: list[Achievement] = []
    total = 0

    all_achievements = await storage.list_achievements()
    for a in all_achievements:
        if a.cv_status == CVStatus.READY:
            continue
        if cv_status is not None and a.cv_status != cv_status:
            continue
        if not a.follow_up_questions:
            continue
        total += 1
        if len(items) >= limit:
            continue
        items.append(a)

    # 按 date desc 排
    items.sort(key=lambda a: a.date, reverse=True)

    return RemindersResponse(items=items, total=total)

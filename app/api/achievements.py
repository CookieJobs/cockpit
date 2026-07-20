"""成就 API。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import storage
from app.core.models import AchievementUpdate, CVStatus

router = APIRouter()


@router.get("")
async def list_achievements(
    project: Optional[str] = Query(None, description="按项目名称过滤"),
    since: Optional[date] = Query(None, description="起始日期 YYYY-MM-DD"),
    only_ready: bool = Query(False, description="只返回 cvStatus=ready（兼容旧参数，新代码用 cv_status）"),
    cv_status: Optional[CVStatus] = Query(None, description="按 cv 状态精确过滤：ready / needs_data / pending"),
):
    """列出成就（按日期倒序）。

    过滤参数优先级：cv_status > only_ready
    """
    items = await storage.list_achievements(
        project_name=project, since=since, only_ready=only_ready, cv_status=cv_status,
    )
    return [a.model_dump(mode="json") for a in items]


@router.patch("/{aid}")
async def update_achievement(aid: str, data: AchievementUpdate):
    """更新成就（只允许更新 cv / cvStatus，符合 append-only 原则）。"""
    achievement = await storage.update_achievement_cv(aid, data)
    if not achievement:
        raise HTTPException(404, "Achievement not found")
    return achievement.model_dump(mode="json")


@router.post("/{aid}/undo")
async def undo_achievement(aid: str):
    """撤销完成（恢复 task，删除 achievement）。"""
    task = await storage.undo_completion(aid)
    if not task:
        raise HTTPException(404, "Achievement not found")
    return task.model_dump(mode="json")

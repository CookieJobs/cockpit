"""成就 API。"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core import storage
from app.core.models import AchievementUpdate, CVStatus

router = APIRouter()


class AnswerFollowUpsRequest(BaseModel):
    """补全追问请求 body (2026-08-01 立)。

    字段:
    - answers: dict[q_idx (str) -> answer (str)], q_idx 是字符串化的整数
      (JSON 对象 key 必须是 string)
    """
    answers: dict[str, str]


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


@router.patch("/{aid}/follow_ups")
async def answer_follow_ups(aid: str, data: AnswerFollowUpsRequest):
    """补全追问 (2026-08-01 立)。

    流程:
    1. 写 follow_up_answers 到 achievement
    2. cv_status 自动升级 ready (用户主动补全了 = 数据够用)
    3. 返更新后的 achievement

    追加: cv_status 已经在 storage.update_achievement_cv 里支持, 这里独立函数
    保持职责清晰 (follow_up 跟 cv 是不同维度的数据, 升级 cv_status 是 follow-up
    补全的副作用, 不是必定的 — 但当前设计里"用户补全了追问" = "数据充分" = ready)。
    """
    # 字符串化 key (Pydantic 自动转, 但防御性写一遍)
    answers = {str(k): v for k, v in data.answers.items()}
    achievement = await storage.answer_follow_ups(aid, answers)
    if not achievement:
        raise HTTPException(404, "Achievement not found")
    return achievement.model_dump(mode="json")

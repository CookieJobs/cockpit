"""任务 API。"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core import storage
from app.core.models import CVStatus, TaskCreate, TaskUpdate

router = APIRouter()


@router.get("")
async def list_tasks(project: Optional[str] = Query(None, description="按项目 ID 过滤")):
    """列出任务。"""
    tasks = await storage.list_tasks(project_id=project)
    return [t.model_dump(mode="json") for t in tasks]


@router.post("")
async def create_task(data: TaskCreate):
    """创建任务（草稿状态）。"""
    try:
        task = await storage.add_task(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return task.model_dump(mode="json")


@router.post("/confirm-drafts")
async def confirm_drafts():
    """确认所有草稿任务。"""
    count = await storage.confirm_all_drafts()
    return {"confirmed": count}


@router.get("/{tid}")
async def get_task(tid: str):
    """获取任务详情。"""
    task = await storage.get_task(tid)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.model_dump(mode="json")


@router.patch("/{tid}")
async def update_task(tid: str, data: TaskUpdate):
    """更新任务。"""
    task = await storage.update_task(tid, data)
    if not task:
        raise HTTPException(404, "Task not found")
    return task.model_dump(mode="json")


@router.delete("/{tid}")
async def delete_task(tid: str):
    """删除任务。"""
    ok = await storage.delete_task(tid)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"ok": True}


@router.post("/{tid}/complete")
async def complete_task(
    tid: str,
    outcome: str = "",
    reflection: str = "",
    cv: str = "",
    cv_status: str = "ready",
):
    """完成任务并沉淀为成就。

    中途崩溃不丢数据：先写 achievement 再删 task。
    """
    try:
        status = CVStatus(cv_status)
    except ValueError:
        raise HTTPException(400, f"Invalid cv_status: {cv_status}")
    achievement = await storage.complete_task(
        tid, outcome=outcome, reflection=reflection, cv=cv, cv_status=status,
    )
    if not achievement:
        raise HTTPException(404, "Task not found")
    return achievement.model_dump(mode="json")

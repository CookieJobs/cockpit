"""任务 API。"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
async def complete_task(tid: str, data: CompleteTaskRequest):
    """完成任务并沉淀为成就。

    4 字段（继承自 task-cockpit skill，对应 Achievement 表 schema）：
    - outcome    必填 — 用户描述的结果
    - cv         必填 — agent 生成的简历级成就陈述
    - reflection 可选 — 主观复盘
    - cv_status  ready/pending 二选一

    中途崩溃不丢数据：先写 achievement 再删 task。

    注意：用 Pydantic BaseModel 接 body，不要用 simple type 参数（FastAPI 会
    当 query 解析，body 整个被忽略 — 修复于 2026-07-16 测试发现）。
    """
    try:
        status = CVStatus(data.cv_status)
    except ValueError:
        raise HTTPException(400, f"Invalid cv_status: {data.cv_status}")
    achievement = await storage.complete_task(
        tid,
        outcome=data.outcome,
        reflection=data.reflection,
        cv=data.cv,
        cv_status=status,
    )
    if not achievement:
        raise HTTPException(404, "Task not found")
    return achievement.model_dump(mode="json")


class CompleteTaskRequest(BaseModel):
    """完成任务请求 body。

    4 字段结构 — 跟 Achievement 表 schema + LLM tool schema 完全一致。
    """
    outcome: str = ""
    reflection: str = ""
    cv: str = ""
    cv_status: str = "ready"


# ===== Checklist 子端点 =====


class ChecklistAddRequest(BaseModel):
    text: str


class ChecklistIndexRequest(BaseModel):
    index: int


@router.post("/{tid}/checklist/add")
async def checklist_add(tid: str, data: ChecklistAddRequest):
    """追加 checklist item。"""
    task = await storage.checklist_add(tid, data.text)
    if not task:
        raise HTTPException(404, "Task not found or empty text")
    return task.model_dump(mode="json")


@router.post("/{tid}/checklist/toggle")
async def checklist_toggle(tid: str, data: ChecklistIndexRequest):
    """切换 checklist item 的 done 状态。"""
    task = await storage.checklist_toggle(tid, data.index)
    if not task:
        raise HTTPException(404, "Task not found or invalid index")
    return task.model_dump(mode="json")


@router.post("/{tid}/checklist/remove")
async def checklist_remove(tid: str, data: ChecklistIndexRequest):
    """删除 checklist item。"""
    task = await storage.checklist_remove(tid, data.index)
    if not task:
        raise HTTPException(404, "Task not found or invalid index")
    return task.model_dump(mode="json")

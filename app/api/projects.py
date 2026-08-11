"""项目 API。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core import storage
from app.core.models import ProjectCreate, ProjectReorderRequest, ProjectUpdate

router = APIRouter()


class AdvancedDeleteRequest(BaseModel):
    project_name: str


@router.get("")
async def list_projects(include_archived: bool = False):
    """列出所有项目。"""
    projects = await storage.list_projects(include_archived=include_archived)
    return [p.model_dump(mode="json") for p in projects]


@router.post("")
async def create_project(data: ProjectCreate):
    """创建项目。"""
    project = await storage.add_project(data)
    return project.model_dump(mode="json")


@router.post("/reorder")
async def reorder_projects(data: ProjectReorderRequest):
    """批量更新项目排序 (2026-07-30 立)。

    前端拖完一次性发, 减少 N 次 PATCH 请求。body = {items: [{id, sort_order}, ...]}。
    返回: {updated: N} — 实际更新的行数 (id 不存在的不计)。
    """
    items = [it.model_dump() for it in data.items]
    updated = await storage.reorder_projects(items)
    return {"updated": updated}


@router.get("/{pid}/danger-preview")
async def danger_preview(pid: str):
    """Show deletion impact before any irreversible action."""
    preview = await storage.project_deletion_preview(pid)
    if not preview:
        raise HTTPException(404, "Project not found")
    return preview


@router.post("/{pid}/danger-delete")
async def danger_delete(pid: str, data: AdvancedDeleteRequest):
    """Advanced-only delete: exact-name confirmation, backup, asset protection."""
    result = await storage.advanced_delete_project(pid, data.project_name)
    if not result:
        raise HTTPException(404, "Project not found")
    if not result["ok"]:
        return JSONResponse(status_code=409, content=result)
    return result


@router.get("/{pid}")
async def get_project(pid: str):
    """获取项目详情。"""
    project = await storage.get_project(pid)
    if not project:
        raise HTTPException(404, "Project not found")
    return project.model_dump(mode="json")


@router.patch("/{pid}")
async def update_project(pid: str, data: ProjectUpdate):
    """更新项目（重命名 / 归档）。"""
    project = await storage.update_project(pid, data)
    if not project:
        raise HTTPException(404, "Project not found")
    return project.model_dump(mode="json")


@router.delete("/{pid}")
async def delete_project(pid: str):
    """项目删除已移至高级设置；普通入口只能归档。"""
    raise HTTPException(405, "Permanent deletion requires the advanced exact-name confirmation flow")

"""项目 API。"""
from fastapi import APIRouter, HTTPException

from app.core import storage
from app.core.models import ProjectCreate, ProjectUpdate

router = APIRouter()


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
    """删除项目（级联删除所有任务）。"""
    ok = await storage.delete_project(pid)
    if not ok:
        raise HTTPException(404, "Project not found")
    return {"ok": True}

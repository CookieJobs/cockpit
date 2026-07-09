"""全局快照 API。"""
from fastapi import APIRouter

from app.core import storage

router = APIRouter()


@router.get("")
async def get_snapshot():
    """获取全局快照：focus 列表 + 按项目分组的任务 + 今日完成 + 计数。

    用于：dashboard 渲染、对话窗口"我现在该干啥"回答。
    """
    snap = await storage.build_snapshot()
    return snap.model_dump(mode="json")

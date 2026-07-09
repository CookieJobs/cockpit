"""WebSocket 端点。

v1.0 简单实现：连接 + 心跳。后续可扩展为事件推送（任务变更实时同步）。
"""
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket 客户端已连接")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # 简单 echo
                await websocket.send_text(json.dumps({"type": "echo", "data": payload}))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开连接")

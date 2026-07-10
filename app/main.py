"""拾光 FastAPI 主入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import storage
from app.api import achievements, chat, chat_sessions, llm, llm_settings, projects, snapshot, tasks, ws

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    logger.info("拾光后端启动，初始化数据库...")
    storage.init_engine()
    await storage.create_tables()
    logger.info("数据库就绪")
    yield
    # 关闭时不需要清理（aiosqlite 自动）


app = FastAPI(
    title="拾光 API",
    version="0.1.0",
    description="你的个人项目驾驶舱",
    lifespan=lifespan,
)

# CORS（开发期允许 3000 端口的 Next.js 前端）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "name": "拾光"}


# 注册路由
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(achievements.router, prefix="/api/achievements", tags=["achievements"])
app.include_router(snapshot.router, prefix="/api/snapshot", tags=["snapshot"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(chat_sessions.router, prefix="/api/chat", tags=["chat-sessions"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(llm_settings.router, prefix="/api/settings", tags=["llm-settings"])
app.include_router(ws.router, tags=["ws"])

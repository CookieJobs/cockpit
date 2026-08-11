"""Cockpit FastAPI 主入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import achievements, chat, chat_sessions, integrations, llm, llm_settings, projects, reminders, snapshot, tasks
from app.core import storage
from app.core.config import settings
from app.main_static import register_static_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库。"""
    logger.info("Cockpit后端启动，初始化数据库...")
    storage.init_engine()
    await storage.create_tables()
    logger.info("数据库就绪")
    yield
    # 关闭时不需要清理（aiosqlite 自动）


app = FastAPI(
    title="Cockpit API",
    version="0.1.0",
    description="你的个人项目驾驶舱",
    lifespan=lifespan,
)

# CORS：
# - 白名单 (allow_origins) 从 COCKPIT_CORS_ORIGINS 读，逗号分隔，prod 严格走这里。
# - dev 模式额外加 allow_origin_regex 匹配 localhost/127.0.0.1 的任意端口，
#   解决前端端口不固定（用户可能在 3001/3005 跑别项目，cockpit 切到 3001+）
#   反复改 CORS 白名单的痛点。dev 放宽到只匹配 loopback, 不暴露外网域名。
# - Docker 部署时前端由 FastAPI 静态服务（同源）不会触发 CORS；
#   如果加 nginx/反代 把前端/后端分开到不同 origin，把反代 origin 加进环境变量。
_cors_origins = [o.strip() for o in settings.cockpit_cors_origins.split(",") if o.strip()]
_is_dev = settings.cockpit_env == "development"
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+" if _is_dev else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    recovery = settings.data_recovery_state()
    return {
        "status": "ok",
        "version": "0.1.0",
        "name": "Cockpit",
        "data_recovery": None if recovery is None else {
            "kind": recovery.kind,
            "message": recovery.message,
            "target": str(recovery.target),
            "misplaced": str(recovery.misplaced),
        },
    }


# 注册路由
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(achievements.router, prefix="/api/achievements", tags=["achievements"])
app.include_router(snapshot.router, prefix="/api/snapshot", tags=["snapshot"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(chat_sessions.router, prefix="/api/chat", tags=["chat-sessions"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(llm_settings.router, prefix="/api/settings", tags=["llm-settings"])
# 2026-08-01: 补全追问提醒端点 (Reminders)
app.include_router(reminders.router, prefix="/api/reminders", tags=["reminders"])
# 2026-08-02: v0.5a.1 接入中心 — 一键把 cockpit MCP server 注册到 Claude Code / Cursor / Trae / Cline / Continue / WorkBuddy
#   router 在 integrations.py 构造时已带 prefix="/api/integrations", 这里不再传 (会双 prefix)
app.include_router(integrations.router)


# ===== 前端静态服务 (Docker 部署时启用) =====
# 委托给 app/main_static.py 模块 — 启用条件 (COCKPIT_ENV=production + web/out 存在)、
# SPA catch-all + 深链接 fallback 逻辑都在那里。
# 必须在所有 API router 之后注册, FastAPI 路由按声明顺序匹配。
register_static_routes(app)

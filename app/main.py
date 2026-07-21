"""Cockpit FastAPI 主入口。"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core import storage
from app.api import achievements, chat, chat_sessions, llm, llm_settings, projects, snapshot, tasks, ws

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

# CORS：白名单从 COCKPIT_CORS_ORIGINS 读，逗号分隔。
# 开发默认只允许 Next.js dev server (3000 端口)。
# Docker 部署时如果前端由 FastAPI 静态服务（同源）不会触发 CORS；
# 如果加 nginx/反代 把前端/后端分开到不同 origin，需要把反代 origin 加进环境变量。
from app.core.config import settings as _settings
_cors_origins = [o.strip() for o in _settings.cockpit_cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0", "name": "Cockpit"}


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


# ===== 前端静态服务 (Docker 部署时启用) =====
# 背景: Next.js 静态导出到 web/out/ 目录, FastAPI 启动时检测到就接管前端服务。
# 单端口方案, 同源 fetch 不会触发 CORS。
# 开发期 (web/out 不存在) 自动跳过, 不会影响 make dev / make web 的体验。
# 注意: SPA catch-all 必须在所有 API router 之后注册, FastAPI 路由按声明顺序匹配。
WEB_DIST = Path(__file__).parent.parent / "web" / "out"
WEB_DIST_INDEX = WEB_DIST / "index.html"

if WEB_DIST_INDEX.exists():
    logger.info(f"检测到前端构建产物 ({WEB_DIST}), 启用静态服务 + SPA catch-all")

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(WEB_DIST_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catchall(full_path: str):
        """SPA catch-all: 任何非 /api/* 的 GET 请求。

        - 真实文件 (CSS/JS/图片) → 直接返回
        - 其它路径 (SPA 路由如 /today /achievements) → 返回 index.html
          让客户端 router 接管
        """
        # 防御: 即使匹配到 api/ws 前缀, FastAPI 已先匹配 router 路由,
        # 不会进到这里。但保险起见显式跳过
        if full_path.startswith("api/") or full_path.startswith("ws"):
            # 实际上不会到这里 (router 已先匹配), 但显式 404 防止 SPA 吞 API 错误
            from fastapi import HTTPException
            raise HTTPException(status_code=404)

        file_path = WEB_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # SPA 路由: 返回 index.html
        return FileResponse(WEB_DIST_INDEX)
else:
    logger.info("未检测到前端构建产物 (web/out), 跳过静态服务 (开发模式正常)")


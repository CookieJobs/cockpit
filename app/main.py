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
#
# 关键 (2026-07-21 修): 用 COCKPIT_ENV=production 作为启用条件, 不只是检测 web/out
# 存在与否。否则本地 dev 场景下:
#   - 用户某次跑过 `npm run build` 生成 web/out/
#   - 之后跑 `make dev` (默认 COCKPIT_ENV=development)
#   - uvicorn 启动时检测到 web/out, 启用静态服务
#   - 浏览器访问 localhost:7842 拿到旧 build 产物, 跟 next dev :3000 状态错位
#   - dev 体验坏掉
# 修法: 只在 COCKPIT_ENV=production 时启用静态服务。本地 dev 用户跑 `make dev`
# 永远走 dev 路径, 不会受 web/out 干扰。docker-compose.yml 已设 COCKPIT_ENV=production。
#
# 同时 (2026-07-21 修): SPA catch-all 之前总是返回 index.html, 深链接 /settings
# 拿到的是主页面 HTML, 引用主页面 chunk, 客户端 React 永远渲染主页面。
# 修法: catch-all 优先尝试 full_path.html (深链接 fallback, Next.js 静态导出
# 的标准行为), 找到返回 settings.html/today.html 等; 找不到再返回 index.html
# (真正的 SPA fallback, 给客户端 router 接管未知路径)。
#
# 注意: SPA catch-all 必须在所有 API router 之后注册, FastAPI 路由按声明顺序匹配。
WEB_DIST = Path(__file__).parent.parent / "web" / "out"
WEB_DIST_INDEX = WEB_DIST / "index.html"

_should_serve_static = (
    WEB_DIST_INDEX.exists() and _settings.cockpit_env == "production"
)

if _should_serve_static:
    logger.info(
        f"检测到前端构建产物 ({WEB_DIST}) + COCKPIT_ENV=production, "
        "启用静态服务 + SPA catch-all"
    )

    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(WEB_DIST_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catchall(full_path: str):
        """SPA catch-all + 深链接 fallback。

        解析顺序 (按 Next.js 静态导出标准):
        1. api/ws 前缀 → 404 (防御, router 已先匹配)
        2. 真实文件 (CSS/JS/图片) → 直接返回
        3. 页面文件 (full_path.html 存在) → 返回深链接 fallback
           例: /settings → out/settings.html → 用户拿到 settings 页面 HTML
        4. 都没有 → 返回 index.html (真正的 SPA fallback)
           例: /today/2023/xyz → 客户端 router 接管
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
        # 深链接 fallback: 尝试 full_path.html
        # 例: /settings → out/settings.html (Next.js 静态导出产物)
        page_path = WEB_DIST / f"{full_path}.html"
        if page_path.is_file():
            return FileResponse(page_path)
        # 真正的 SPA fallback: 未知路径返回 index.html, 客户端 router 接管
        return FileResponse(WEB_DIST_INDEX)
elif WEB_DIST_INDEX.exists() and _settings.cockpit_env != "production":
    logger.info(
        f"检测到 web/out/ 但 COCKPIT_ENV={_settings.cockpit_env!r}, "
        "跳过静态服务 (避免本地 dev 拿到旧 build, 保持 dev 体验纯净). "
        "用 `make web` 跑 next dev :3000, 或显式 COCKPIT_ENV=production 启用静态服务."
    )
else:
    logger.info("未检测到前端构建产物 (web/out), 跳过静态服务 (开发模式正常)")


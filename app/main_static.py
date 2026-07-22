"""前端静态服务 + SPA catch-all (2026-07-22 抽)。

背景: Next.js 静态导出到 web/out/ 目录, FastAPI 启动时检测到就接管前端服务。
单端口方案, 同源 fetch 不会触发 CORS。

启用条件 (2026-07-21 修): 用 COCKPIT_ENV=production 作为启用条件, 不只是检测
web/out 存在与否。否则本地 dev 场景下:
  - 用户某次跑过 `npm run build` 生成 web/out/
  - 之后跑 `make dev` (默认 COCKPIT_ENV=development)
  - uvicorn 启动时检测到 web/out, 启用静态服务
  - 浏览器访问 localhost:7842 拿到旧 build 产物, 跟 next dev :3000 状态错位
  - dev 体验坏掉

SPA catch-all (2026-07-21 修): 之前总是返回 index.html, 深链接 /settings
拿到的是主页面 HTML, 引用主页面 chunk, 客户端 React 永远渲染主页面。
修法: catch-all 优先尝试 full_path.html (深链接 fallback, Next.js 静态导出
的标准行为), 找到返回 settings.html/today.html 等; 找不到再返回 index.html
(真正的 SPA fallback, 给客户端 router 接管未知路径)。

注意: SPA catch-all 必须在所有 API router 之后注册 (调用 register() 时机
由 main.py 控制), FastAPI 路由按声明顺序匹配。
"""
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).parent.parent / "web" / "out"
WEB_DIST_INDEX = WEB_DIST / "index.html"


def register_static_routes(app: FastAPI) -> None:
    """如果满足启用条件, 注册前端静态服务 + SPA catch-all 到 app。

    调用方: main.py 模块顶层调用一次, 因为 SPA catch-all 必须在所有 API
    router 之后注册, FastAPI 路由按声明顺序匹配。
    """
    if not WEB_DIST_INDEX.exists():
        logger.info("未检测到前端构建产物 (web/out), 跳过静态服务 (开发模式正常)")
        return

    if settings.cockpit_env != "production":
        logger.info(
            f"检测到 web/out/ 但 COCKPIT_ENV={settings.cockpit_env!r}, "
            "跳过静态服务 (避免本地 dev 拿到旧 build, 保持 dev 体验纯净). "
            "用 `make web` 跑 next dev :3000, 或显式 COCKPIT_ENV=production 启用静态服务."
        )
        return

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
        1. api 前缀 → 404 (防御, router 已先匹配)
        2. 真实文件 (CSS/JS/图片) → 直接返回
        3. 页面文件 (full_path.html 存在) → 返回深链接 fallback
           例: /settings → out/settings.html → 用户拿到 settings 页面 HTML
        4. 都没有 → 返回 index.html (真正的 SPA fallback)
           例: /today/2023/xyz → 客户端 router 接管
        """
        # 防御: 即使匹配到 api 前缀, FastAPI 已先匹配 router 路由,
        # 不会进到这里。但保险起见显式 404 防止 SPA 吞 API 错误
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)

        file_path = WEB_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # 深链接 fallback: 尝试 full_path.html
        page_path = WEB_DIST / f"{full_path}.html"
        if page_path.is_file():
            return FileResponse(page_path)
        # 真正的 SPA fallback: 未知路径返回 index.html, 客户端 router 接管
        return FileResponse(WEB_DIST_INDEX)

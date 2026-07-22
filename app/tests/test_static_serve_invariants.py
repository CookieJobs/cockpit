"""FastAPI 静态服务 + SPA catch-all 不变量测试 (2026-07-21 立, 2026-07-22 更新)。

背景:
覆盖两个历史 bug:
1. SPA catch-all 总是返回 index.html, 深链接 /settings 拿不到 settings.html
   → 客户端 React 永远渲染主页面, /settings 进不去
2. 静态服务只看 web/out 存在与否, 不看 COCKPIT_ENV, 本地 dev 会被旧 build
   产物污染 (`make dev` 启动时检测到 web/out/ 启用静态服务, 跟 next dev
   :3000 状态错位, dev 体验坏掉)

不变量锁住 4 条:
1. SPA catch-all 必须先尝试 full_path.html (深链接 fallback)
2. SPA catch-all 最后才返回 index.html (真正的 SPA fallback)
3. 静态服务启用条件: web/out/index.html 存在 AND COCKPIT_ENV=production
4. dev/test 模式下即使 web/out/ 存在也不能启用静态服务

2026-07-22 更新: 静态服务逻辑从 main.py 抽到 app/main_static.py 模块
(register_static_routes 函数)。测试扫描位置从 main.py 改成 main_static.py。
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).parent.parent.parent / "app"
MAIN_STATIC_PY = APP_DIR / "main_static.py"


def read_main_static() -> str:
    return MAIN_STATIC_PY.read_text(encoding="utf-8")


def find_spa_catchall(src: str) -> str:
    """提取 spa_catchall 函数的函数体 (粗略, 不严格配对).

    2026-07-22 重构: spa_catchall 现在嵌套在 register_static_routes 内部 (4 空格缩进),
    不是顶层函数。原 regex 找顶层的 `async def`, 现改成允许任意缩进前缀。
    `.*?` 非贪婪匹配函数签名 (避免 `[^)]*` 在 `full_path: str)` 处截断)。
    """
    m = re.search(
        r"^\s*async\s+def\s+spa_catchall\(.*?\):\s*(.*?)(?=\n\s*@|\n\s*(?:def|async\s+def)\s|\Z)",
        src,
        re.DOTALL | re.MULTILINE,
    )  # noqa: W605
    assert m, "app/main_static.py 找不到 spa_catchall 函数"
    return m.group(1)
    assert m, "app/main_static.py 找不到 spa_catchall 函数"
    return m.group(1)


def find_register_static_routes(src: str) -> str:
    r"""提取 register_static_routes 函数体 (顶层 def, 不被内部嵌套函数截断)。

    用 `.*?` 非贪婪匹配函数签名 (避免 `[^)]*` 在 `FastAPI)` 处截断),
    结束标志: 下一个顶层 def/class/@decorator 或文件末尾 (\Z)。
    """
    m = re.search(
        r"^def\s+register_static_routes\(.*?\):\s*(.*?)(?=\n@|\n(def|class)\s|\Z)",
        src,
        re.DOTALL | re.MULTILINE,
    )  # noqa: W605
    assert m, "app/main_static.py 找不到 register_static_routes 函数"
    return m.group(1)
    assert m, "app/main_static.py 找不到 register_static_routes 函数"
    return m.group(1)


def test_spa_catchall_tries_full_path_html():
    """SPA catch-all 必须先尝试 full_path.html (Next.js 静态导出深链接标准行为)。

    历史 bug (2026-07-21): catch-all 总是返回 index.html, 用户访问 /settings
    拿到的是主页面 HTML (引用主页面 chunk), 客户端 React 渲染主页面, /settings
    永远进不去。修法: 加 'page_path = WEB_DIST / f"{full_path}.html"' 检查。

    2026-07-22 更新: 抽到 main_static.py 后, 测试扫描位置改成 main_static.py。
    """
    body = find_spa_catchall(read_main_static())
    assert '"{full_path}.html"' in body or "f'{full_path}.html'" in body, (
        "spa_catchall 缺深链接 fallback: 没尝试 full_path.html 文件。\n"
        "Next.js 静态导出产物是 settings.html / today.html / report.html 等, "
        "用户访问 /settings 应返回 settings.html, 客户端 React 看到正确的 "
        "page chunk 才能渲染 settings 页面。\n"
        "修法: 在 file_path 检查之后加 'page_path = WEB_DIST / f\"{full_path}.html\"; "
        "if page_path.is_file(): return FileResponse(page_path)'"
    )


def test_spa_catchall_falls_back_to_index():
    """SPA catch-all 最后才返回 index.html (真正的 SPA fallback, 给客户端 router 接管未知路径)。"""
    body = find_spa_catchall(read_main_static())
    # 期望 return FileResponse(WEB_DIST_INDEX) 至少出现一次
    assert body.count("return FileResponse(WEB_DIST_INDEX)") >= 1, (
        "spa_catchall 缺 index.html fallback。未知路径 (如 /today/2023/xyz) 应该 "
        "返回 index.html 让客户端 router 接管, 否则用户访问任何非预渲染路径都 404"
    )


def test_static_serve_requires_production_env():
    """静态服务启用条件: web/out 存在 AND COCKPIT_ENV=production。

    2026-07-22 重构: 启用条件在 main_static.py 的 register_static_routes 函数里
    (用 if not exists return / if env != production return 守卫), 不再用
    _should_serve_static 变量。测试扫描新逻辑。
    """
    src = read_main_static()
    # 找 register_static_routes 函数
    assert "register_static_routes" in src, (
        "app/main_static.py 必须暴露 register_static_routes(app) 函数供 main.py 调用"
    )
    # 必须有两个守卫: exists check + production env check
    assert "WEB_DIST_INDEX.exists()" in src, (
        "静态服务启用条件缺 WEB_DIST_INDEX.exists() 检查。必须检测 web/out 存在"
    )
    assert "cockpit_env" in src and '"production"' in src, (
        "静态服务启用条件缺 COCKPIT_ENV==production 守卫。\n"
        "如果只看 web/out 存在, 本地 dev 跑过 npm run build 之后再跑 make dev, "
        "uvicorn 会启用静态服务, 浏览器拿旧 build 跟 next dev :3000 状态错位, "
        "dev 体验坏掉。修法: register_static_routes 必须 return 守卫 if env != production"
    )


def test_dev_env_skips_static_serve_with_existing_out():
    """dev/test 模式下即使 web/out/ 存在也不能启用静态服务 (有 log 警告分支)。

    验证 main_static.py 的 dev 分支显式 log 跳过, 避免静默走错路径。
    """
    src = read_main_static()
    body = find_register_static_routes(src)
    # dev 分支必须显式 log 跳过
    assert "COCKPIT_ENV=" in body, (
        "register_static_routes 缺 dev 模式跳过日志 (应含 'COCKPIT_ENV=' 字样)。"
        "dev 模式需要明确 log 跳过原因, 不能静默"
    )
    assert "跳过静态服务" in body, (
        "register_static_routes 缺 dev 模式跳过的中文提示。"
        "用户跑 `make dev` 时 uvicorn 日志应明确'跳过静态服务'原因, 避免困惑"
    )


def test_main_uses_main_static_module():
    """app/main.py 必须通过 register_static_routes() 调用 main_static, 不能自己实现静态服务。

    2026-07-22 重构: 静态服务从 main.py 抽到 main_static.py 模块, main.py 必须 import
    + 调用, 不能再次重复实现 (防回退)。
    """
    main_py = (Path(__file__).parent.parent.parent / "app" / "main.py").read_text(encoding="utf-8")
    assert "from app.main_static import" in main_py or "from .main_static import" in main_py, (
        "app/main.py 没 import main_static 模块, 静态服务逻辑在 main.py 重复实现了。"
        "2026-07-22 重构要求 main.py 通过 register_static_routes(app) 调用 main_static, "
        "main.py 本身不应再有 _should_serve_static / spa_catchall / FileResponse 这些。"
        "修法: 加 'from app.main_static import register_static_routes' + 模块顶层调一次"
    )
    assert "register_static_routes(app)" in main_py, (
        "app/main.py 没调用 register_static_routes(app), 静态服务没被注册到 FastAPI app"
    )
    # 防止 main.py 又自己实现 FileResponse / spa_catchall (回退)
    assert "spa_catchall" not in main_py, (
        "app/main.py 又出现了 spa_catchall 函数定义, 2026-07-22 重构要求抽到 main_static.py"
    )
    assert "WEB_DIST" not in main_py, (
        "app/main.py 又出现了 WEB_DIST 变量, 2026-07-22 重构要求抽到 main_static.py"
    )

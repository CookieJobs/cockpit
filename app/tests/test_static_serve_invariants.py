"""FastAPI 静态服务 + SPA catch-all 不变量测试 (2026-07-21 立)。

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
"""
import re
from pathlib import Path

APP_DIR = Path(__file__).parent.parent.parent / "app"
MAIN_PY = APP_DIR / "main.py"


def read_main() -> str:
    return MAIN_PY.read_text(encoding="utf-8")


def find_spa_catchall(src: str) -> str:
    """提取 spa_catchall 函数的函数体 (粗略, 不严格配对)."""
    m = re.search(
        r"async\s+def\s+spa_catchall\([^)]*\):\s*(.*?)(?=\n@|\n    def\s|\n    async\s|\nelif\s|\nelse\s|\nif\s+__name)",
        src,
        re.DOTALL,
    )
    assert m, "app/main.py 找不到 spa_catchall 函数"
    return m.group(1)


def test_spa_catchall_tries_full_path_html():
    """SPA catch-all 必须先尝试 full_path.html (Next.js 静态导出深链接标准行为)。

    历史 bug (2026-07-21): catch-all 总是返回 index.html, 用户访问 /settings
    拿到的是主页面 HTML (引用主页面 chunk), 客户端 React 渲染主页面, /settings
    永远进不去。修法: 加 'page_path = WEB_DIST / f"{full_path}.html"' 检查。
    """
    body = find_spa_catchall(read_main())
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
    body = find_spa_catchall(read_main())
    # 期望 return FileResponse(WEB_DIST_INDEX) 至少出现一次
    assert body.count("return FileResponse(WEB_DIST_INDEX)") >= 1, (
        "spa_catchall 缺 index.html fallback。未知路径 (如 /today/2023/xyz) 应该 "
        "返回 index.html 让客户端 router 接管, 否则用户访问任何非预渲染路径都 404"
    )


def test_static_serve_requires_production_env():
    """静态服务启用条件: web/out 存在 AND COCKPIT_ENV=production。

    避免本地 dev 被旧 build 污染。
    """
    src = read_main()
    # 找 _should_serve_static 定义
    m = re.search(
        r"_should_serve_static\s*=\s*([\s\S]+?)\n\n",
        src,
    )
    assert m, "app/main.py 找不到 _should_serve_static 定义 (静态服务启用条件)"
    expr = m.group(1)
    # 期望: WEB_DIST_INDEX.exists() AND settings.cockpit_env == "production"
    assert "WEB_DIST_INDEX.exists()" in expr, (
        "静态服务启用条件缺 WEB_DIST_INDEX.exists() 检查。必须检测 web/out 存在"
    )
    assert 'cockpit_env' in expr and 'production' in expr, (
        "静态服务启用条件缺 COCKPIT_ENV==production 守卫。\n"
        "如果只看 web/out 存在, 本地 dev 跑过 npm run build 之后再跑 make dev, "
        "uvicorn 会启用静态服务, 浏览器拿旧 build 跟 next dev :3000 状态错位, "
        "dev 体验坏掉。修法: _should_serve_static = WEB_DIST_INDEX.exists() and "
        "settings.cockpit_env == 'production'"
    )


def test_dev_env_skips_static_serve_with_existing_out():
    """dev/test 模式下即使 web/out/ 存在也不能启用静态服务 (有 elif 警告分支)。

    验证代码里至少有一个 elif/else 分支显式 log 跳过, 避免静默走错路径。
    """
    src = read_main()
    # 找 _should_serve_static 判断的完整 if/elif/else 块
    m = re.search(
        r"if\s+_should_serve_static:[\s\S]*?(?=\n# ====|\n# ===|\n#  |\n#  )",
        src,
    )
    if m:
        block = m.group(0)
        # 至少要有 elif 或 else 处理 dev 情况
        assert "elif" in block or "else" in block, (
            "app/main.py 静态服务块缺 elif/else 守卫。dev 模式需要明确 log 跳过, "
            "而不是默认启用 (那会跟 dev 体验冲突)"
        )
    else:
        # 退路: 找整个 _should_serve_static 上下文, 看有没有 dev 警告
        idx = src.find("_should_serve_static")
        ctx = src[idx : idx + 3000]
        assert "elif" in ctx or 'COCKPIT_ENV=' in ctx, (
            "app/main.py 缺 dev 模式跳过静态服务的警告逻辑 (elif WEB_DIST_INDEX.exists() "
            "and ... != production, log 跳过)"
        )

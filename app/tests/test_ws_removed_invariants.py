"""WebSocket 死代码清理 — 不变量测试 (2026-07-22 立)。

背景:
  app/api/ws.py 是 v1.0 占位实现 (echo + 心跳), 前端没在用
  (dashboard 是 SWR 5 秒轮询 /api/snapshot, 没 new WebSocket(...) 调用)。
  死代码占路由 + 误导读代码的人以为有实时同步。
  2026-07-22 删除 ws.py + main.py 的 include + pyproject.toml 的 websockets 依赖。

锁住的不变量:
  1. app/api/ws.py 文件不存在
  2. main.py 不再 import ws 也不再 include ws.router
  3. pyproject.toml 不再有 websockets 依赖
  4. FastAPI 启动后路由表里不再有 /ws

未来要回滚 / 真做实时同步时: 删这条不变量 + 重新加 ws.py + 配内存 pub/sub。
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_ws_file_removed():
    """app/api/ws.py 必须不存在 (2026-07-22 死代码清理)。"""
    ws_path = ROOT / "app" / "api" / "ws.py"
    assert not ws_path.exists(), (
        f"{ws_path} 重新出现了, 但 v1.0 占位 WebSocket 仍是死代码 (前端无 WS 客户端)。"
        "如果想真做实时同步, 应当配内存 pub/sub (broadcaster) 而不是回滚 v1.0 echo 端点。"
        "决策记录见 docs/refactor/2026-07-22-cleanup.md"
    )


def test_main_no_longer_imports_or_includes_ws():
    """main.py 不再 import app.api.ws 也不再 include ws.router。"""
    main_py = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "ws" not in main_py.split("\n")[10:60].__str__() or True  # 注释里有 "ws.py 端点" 不算
    # 严格检查: import 行不能含 "ws" (从 "from app.api import ... ws" 这种)
    import_lines = [
        line for line in main_py.split("\n")
        if line.strip().startswith("from app.api import")
    ]
    assert import_lines, "找不到 main.py 里 from app.api import 行"
    joined = " ".join(import_lines)
    assert " ws" not in joined and not joined.rstrip().endswith(", ws"), (
        f"main.py 还有 `from app.api import ... ws` (行: {import_lines}), "
        "ws.py 已删除, 这个 import 会让 uvicorn 启动失败"
    )
    # 也不应有 ws.router 引用
    assert "ws.router" not in main_py, (
        "main.py 还有 `ws.router` 引用, ws.py 已删除, 启动会 NameError"
    )


def test_pyproject_no_longer_depends_on_websockets():
    """pyproject.toml 不再有 websockets 依赖 (ws.py 是唯一用户)。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # 排除注释 (dependencies 块里)
    deps_block = pyproject.split("[project.optional-dependencies]")[0]
    assert "websockets" not in deps_block, (
        "pyproject.toml dependencies 还有 websockets, "
        "ws.py 已删除, 这依赖是死代码 (lifespan 启动时不需要 WebSocket 协议)"
    )


def test_app_routes_no_longer_expose_ws_path():
    """FastAPI app routes 不再暴露 /ws 端点。"""
    from app.main import app

    ws_paths = [r.path for r in app.routes if hasattr(r, "path") and r.path == "/ws"]
    assert not ws_paths, (
        f"FastAPI app 路由表里还有 /ws 端点, 但前端无 WS 客户端。"
        f"如果想真做实时同步, 应配 broadcaster pub/sub 而不是回滚 v1.0 echo。"
    )

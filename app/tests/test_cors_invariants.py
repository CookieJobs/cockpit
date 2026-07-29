"""CORS 配置不变量测试 (2026-07-25 立)。

背景：dev 模式以前硬编码只允许 3000 端口, 用户 3000 跑别的项目时 cockpit
切到 3001 → 所有 preflight 被拒, 浏览器报 "Failed to fetch"。
修法：app/main.py 的 CORSMiddleware 在 dev 模式额外加 allow_origin_regex
匹配 localhost/127.0.0.1 任意端口, prod 模式严格走白名单。

本测试锁住：
1. dev 模式 CORSMiddleware 必须有 allow_origin_regex 匹配 loopback 任意端口
2. dev 模式从 localhost/127.0.0.1 的任意端口 preflight 必须 200
3. dev 模式从非 loopback origin preflight 必须 400 (不放宽到外网)
4. prod 模式 allow_origin_regex 必须是 None (不破现有安全假设)
5. 静态不变量: main.py 必须有 `allow_origin_regex=...if _is_dev else None` 模式
   防后人误删 dev 放宽逻辑
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ===== 1. 静态 introspect dev 模式配置 =====

def test_dev_mode_cors_middleware_has_localhost_any_port_regex():
    """dev 模式 CORSMiddleware 必须有 allow_origin_regex 匹配 localhost/127.0.0.1 任意端口。

    用 app.user_middleware introspect 实际生效的 kwargs, 防 "代码改了但配置没生效"。
    """
    from app.main import app

    cors_mw = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_mw is not None, "找不到 CORSMiddleware 配置"

    regex = cors_mw.kwargs.get("allow_origin_regex")
    assert regex is not None, (
        "dev 模式必须有 allow_origin_regex 放宽到 localhost 任意端口, "
        "否则前端换端口又会全断 (2026-07-25 教训)"
    )
    # 必须能匹配 localhost:任意端口
    assert re.match(regex, "http://localhost:3000")
    assert re.match(regex, "http://localhost:3001")
    assert re.match(regex, "http://localhost:3005")
    assert re.match(regex, "http://127.0.0.1:3000")
    assert re.match(regex, "http://127.0.0.1:3001")
    # 不能匹配外网域名 (安全: dev 放宽不能泄到外网)
    assert not re.match(regex, "https://example.com")
    assert not re.match(regex, "http://evil.com:3000")


# ===== 2. 实际 preflight 行为 (dev 模式) =====

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_dev_preflight_from_localhost_any_port_passes(client):
    """dev 模式从 localhost/127.0.0.1 任意端口 OPTIONS 必须 200。

    覆盖实际用户场景: 3000 跑了别的项目, cockpit 切到 3001, 仍能通。
    """
    for origin in [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3005",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]:
        r = client.options(
            "/api/chat/sessions",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert r.status_code == 200, f"dev 模式 {origin} preflight 应该是 200, 实际 {r.status_code}: {r.text}"
        assert r.headers.get("access-control-allow-origin") == origin, (
            f"dev 模式 {origin} 应回 ACAO={origin}, 实际 {r.headers.get('access-control-allow-origin')}"
        )


def test_dev_preflight_from_non_loopback_origin_rejected(client):
    """dev 模式从外网 origin preflight 必须 400。

    安全：放宽 regex 只匹配 loopback, 不能泄到外网域名。
    """
    r = client.options(
        "/api/chat/sessions",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 400, (
        f"dev 模式外网 origin 应该被拒, 实际 {r.status_code}: {r.text}"
    )


# ===== 3. 静态不变量: 防代码回退 =====

def test_main_py_cors_regex_branches_on_dev_env():
    """main.py 必须有 `allow_origin_regex=...if _is_dev else None` 模式。

    防止后人简化成 `allow_origin_regex=None` (硬关) 或 `allow_origin_regex="*"`
    (过度放宽) 两种回退路径。
    """
    main_py = Path(__file__).parent.parent / "main.py"
    src = main_py.read_text(encoding="utf-8")

    # 必须有 allow_origin_regex=
    assert "allow_origin_regex=" in src, "main.py 缺少 allow_origin_regex 配置"

    # 必须跟 _is_dev 联动 (三元表达式)
    pattern = re.compile(
        r"allow_origin_regex\s*=\s*[^,\n]*if\s+_is_dev\s+else\s+None",
        re.MULTILINE,
    )
    assert pattern.search(src), (
        "main.py 的 allow_origin_regex 必须用 `...if _is_dev else None` 三元式, "
        "确保 dev 放宽 / prod 严格 两个分支都在"
    )


def test_main_py_dev_regex_matches_loopback_not_external():
    """dev 模式 regex 必须显式匹配 localhost/127.0.0.1, 不能是 `.*` 或 `*` 这种危险模式。"""
    main_py = Path(__file__).parent.parent / "main.py"
    src = main_py.read_text(encoding="utf-8")

    # 抓 dev 分支的 regex 字面量
    m = re.search(
        r"allow_origin_regex\s*=\s*([^,\n]+?)\s+if\s+_is_dev",
        src,
    )
    assert m, "找不到 dev 分支 regex"
    regex_literal = m.group(1).strip().strip("'\"")

    # 必须含 localhost 或 127.0.0.1
    assert "localhost" in regex_literal or "127.0.0.1" in regex_literal, (
        f"dev regex 必须匹配 loopback, 实际: {regex_literal}"
    )
    # 不能是 `.*` / `.+` 这种"全匹配"
    assert regex_literal not in (".*", ".+", "*"), (
        f"dev regex 过度放宽到 {regex_literal}, 这是安全风险"
    )

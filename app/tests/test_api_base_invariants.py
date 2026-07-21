"""API_BASE / NEXT_PUBLIC_API_BASE 不变量测试 (2026-07-21 立)。

历史 bug (按时间顺序, 两次踩同一个坑):
1. .env.local 优先级高于 .env.production, 部署后前端 fetch 连本机
   127.0.0.1:7842 (没服务) → "Failed to fetch"
2. (错误修法) 设 NEXT_PUBLIC_API_BASE=/api, 但 lib/api.ts 里 path 本身已
   含 /api/... 前缀, 拼接后变 /api/api/... → 404
3. (正确修法) 设 NEXT_PUBLIC_API_BASE="" (空字符串), fetch 走相对路径,
   浏览器自动用当前 origin 拼, lib/api.ts 里的 path 自带 /api/... 完整

不变量锁住 4 条:
1. Dockerfile 阶段 1 (frontend-builder) 必须显式 ARG NEXT_PUBLIC_API_BASE=""
2. web/.env.production 必须设 NEXT_PUBLIC_API_BASE= (空)
3. web/lib/api.ts 生产 fallback 必须是空字符串 (相对路径), 不是 localhost
4. web/lib/api.ts 开发 fallback 仍是 127.0.0.1:7842 (保持 dev 体验)
"""
import re
from pathlib import Path

WEB_DIR = Path(__file__).parent.parent.parent / "web"
DOCKERFILE = Path(__file__).parent.parent.parent / "Dockerfile"
API_TS = WEB_DIR / "lib" / "api.ts"
ENV_PRODUCTION = WEB_DIR / ".env.production"


def test_dockerfile_injects_empty_next_public_api_base():
    """Dockerfile 阶段 1 必须显式 ARG NEXT_PUBLIC_API_BASE="" (空字符串)。

    不显式注入, 本地 .env.local 里的 127.0.0.1:7842 会 inline 进 bundle,
    部署后 fetch 连你本机 7842 (没服务) → "Failed to fetch"。
    也不能是 /api (会双前缀, path 已含 /api/... 前缀)。
    """
    src = DOCKERFILE.read_text(encoding="utf-8")
    m = re.search(
        r"FROM\s+node:[^\n]+AS\s+frontend-builder(.*?)FROM\s+python:",
        src,
        re.DOTALL,
    )
    assert m, "Dockerfile 找不到 frontend-builder 阶段 (FROM node:... AS frontend-builder)"
    stage = m.group(1)
    assert "NEXT_PUBLIC_API_BASE" in stage, (
        "Dockerfile 阶段 1 没显式注入 NEXT_PUBLIC_API_BASE. 本地 web/.env.local 会 "
        "inline 进 bundle, 部署后 fetch 连本机 7842 → 'Failed to fetch' "
        "(历史 bug 2026-07-21). 修法: 在 frontend-builder 阶段加 "
        "'ARG NEXT_PUBLIC_API_BASE=\"\"' + 'ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}'"
    )
    # 必须是空字符串, 不能是 /api (会双前缀)
    arg_match = re.search(
        r'ARG\s+NEXT_PUBLIC_API_BASE\s*=\s*("[^"]*"|\S+)',
        stage,
    )
    assert arg_match, "Dockerfile ARG NEXT_PUBLIC_API_BASE 没找到"
    arg_value = arg_match.group(1).strip('"')
    assert arg_value == "", (
        f"Dockerfile ARG NEXT_PUBLIC_API_BASE={arg_value!r}, 应是空字符串 ''. "
        "设为 /api 会双前缀 (lib/api.ts 的 path 已自带 /api/... 前缀, 拼接变 /api/api/...)"
    )


def test_env_production_is_empty():
    """web/.env.production NEXT_PUBLIC_API_BASE 必须是空字符串。

    Dockerfile build 时 .env.production 也会被读 (优先级低于 ARG 但仍生效
    于 react component), 保持一致避免歧义。
    """
    src = ENV_PRODUCTION.read_text(encoding="utf-8")
    # 找 NEXT_PUBLIC_API_BASE= 后面的值
    m = re.search(r'NEXT_PUBLIC_API_BASE\s*=\s*(\S*)', src)
    assert m, "web/.env.production 找不到 NEXT_PUBLIC_API_BASE=..."
    value = m.group(1).strip('"').strip("'")
    assert value == "", (
        f"web/.env.production NEXT_PUBLIC_API_BASE={value!r}, 应是空字符串 ''. "
        "设非空会让生产 build 出来的 JS 走绝对地址 (踩 127.0.0.1:7842 坑) 或双前缀"
    )


def test_api_ts_production_fallback_is_empty():
    """web/lib/api.ts 在生产 build 时 fallback 必须是空字符串 (相对路径)。"""
    src = API_TS.read_text(encoding="utf-8")
    m = re.search(r"const\s+API_BASE\s*=\s*([\s\S]+?);", src)
    assert m, "web/lib/api.ts 找不到 const API_BASE = ...; 声明"
    rhs = m.group(1)
    assert "_isDev" in rhs, (
        "API_BASE fallback 没用 _isDev 三元, 区分不出 dev/prod. "
        "修法: const _isDev = process.env.NODE_ENV === 'development'; "
        "const API_BASE = process.env.NEXT_PUBLIC_API_BASE || (_isDev ? 'http://127.0.0.1:7842' : '');"
    )
    prod_fallback_match = re.search(
        r'_isDev\s*\?\s*"[^"]*"\s*:\s*"([^"]*)"',
        rhs,
    )
    assert prod_fallback_match, "API_BASE 缺 _isDev ? 'dev_url' : 'prod_url' 三元结构"
    prod_fallback = prod_fallback_match.group(1)
    assert prod_fallback == "", (
        f"API_BASE 生产 fallback = {prod_fallback!r}, 应是空字符串 '' (相对路径). "
        "非空会让生产 build inline 绝对地址, 部署后 fetch 连错地方 (历史 bug 2026-07-21)"
    )


def test_api_ts_dev_fallback_preserved():
    """web/lib/api.ts 开发 fallback 仍是 http://127.0.0.1:7842 (保 dev 体验)。"""
    src = API_TS.read_text(encoding="utf-8")
    m = re.search(r"const\s+API_BASE\s*=\s*([\s\S]+?);", src)
    assert m
    rhs = m.group(1)
    dev_fallback_match = re.search(r'_isDev\s*\?\s*"([^"]*)"', rhs)
    assert dev_fallback_match, "API_BASE 缺 _isDev ? 'dev_url' 三元 dev 分支"
    dev_fallback = dev_fallback_match.group(1)
    assert "127.0.0.1:7842" in dev_fallback, (
        f"API_BASE 开发 fallback = {dev_fallback!r}, 应是 127.0.0.1:7842. "
        "改成其他值会让本地 dev 体验坏掉 (next dev 3000 端口 fetch 走后端 7842)"
    )

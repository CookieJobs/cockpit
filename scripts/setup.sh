#!/usr/bin/env bash
# Cockpit 首次环境准备。
# 跑过之后不需要再跑（除非删了 .venv 或 web/node_modules）。
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> [1/4] Python venv..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  echo "    已创建 .venv"
else
  echo "    .venv 已存在，跳过"
fi

echo "==> [2/4] Python 依赖（含 dev 测试工具）..."
.venv/bin/pip install -e ".[dev]"

echo "==> [3/4] .env 配置..."
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
  echo "    已生成 .env（暂时可以空着，后面去 Web UI 设置页配 LLM）"
else
  echo "    .env 已存在，跳过"
fi

echo "==> [4/5] 前端依赖..."
if [ ! -d "web/node_modules" ]; then
  (cd web && npm install)
  echo "    已装 web/node_modules"
else
  echo "    web/node_modules 已存在，跳过"
fi

echo "==> [5/5] 前端 .env.local..."
if [ ! -f "web/.env.local" ] && [ -f "web/.env.example" ]; then
  cp web/.env.example web/.env.local
  echo "    已生成 web/.env.local（默认指向 http://127.0.0.1:7842）"
else
  echo "    web/.env.local 已存在或无模板，跳过"
fi

# ===== Smoke test: 后端真能起来吗？=====
# 背景 (lesson #8): 之前用户跑完 setup → 起服务 → 端口 0 监听, 抓瞎才发现
#   是 greenlet 漏装 / FastAPI 注解 NameError 等隐藏坑。setup 装依赖 ≠
#   服务能起, 这两件事得分开验证。
#
# 做法: 后台起 uvicorn (默认端口 7842), sleep 3 等初始化, curl /api/health,
#   杀进程, 输出 ✅ / ❌。失败不让整个 setup exit (用户已经准备好环境了,
#   警告一下即可, 不然跑 make 都跑不了)。
#
# 端口用 COCKPIT_PORT 环境变量, 默认 7842。CI / 多实例场景可覆盖。
echo "==> [6/6] Smoke test (uvicorn + /api/health)..."
SMOKE_PORT="${COCKPIT_PORT:-7842}"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$SMOKE_PORT" --log-level warning >/tmp/cockpit-smoke.log 2>&1 &
SMOKE_PID=$!
SMOKE_HEALTHY=0
# 最多等 10 秒, 每 1 秒 ping 一次 (启动 + DB init + lifespan 有时慢)
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  if curl -sf "http://127.0.0.1:$SMOKE_PORT/api/health" >/dev/null 2>&1; then
    SMOKE_HEALTHY=1
    break
  fi
done
# 不管成功失败, 都杀掉 uvicorn (后台进程不能让 setup 留 zombie)
kill "$SMOKE_PID" 2>/dev/null || true
wait "$SMOKE_PID" 2>/dev/null || true
if [ "$SMOKE_HEALTHY" -eq 1 ]; then
  echo "    ✅ 后端能正常启动 (http://127.0.0.1:$SMOKE_PORT/api/health 响应 ok)"
else
  echo "    ⚠️  Smoke test 失败 — 后端没在 10 秒内起来, /api/health 不通"
  echo "       这通常意味着依赖漏装 / 隐式 import 错 / 端口被占"
  echo "       完整日志: /tmp/cockpit-smoke.log (最后 20 行 ↓)"
  tail -20 /tmp/cockpit-smoke.log 2>/dev/null | sed 's/^/         /'
  echo "       环境已就绪, 仍可跑 'make dev' 重试, 但需要修根因"
fi

echo ""
echo "==> ✅ 环境准备好（服务还没启动，需要再跑一条启动命令）"
echo ""
echo "==> 启动服务（任选其一）："
echo "    make all          # 一终端起后端+前端（推荐：最简单）"
echo "    make dev          # 终端 1：后端  http://localhost:7842"
echo "    make web          # 终端 2：前端  http://localhost:3000"
echo ""
echo "==> 启动后再访问："
echo "    http://localhost:3000  → 右上角 ⚙️ 配 LLM"

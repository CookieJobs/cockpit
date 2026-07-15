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

echo "==> [4/4] 前端依赖..."
if [ ! -d "web/node_modules" ]; then
  (cd web && npm install)
  echo "    已装 web/node_modules"
else
  echo "    web/node_modules 已存在，跳过"
fi

echo ""
echo "==> ✅ 环境准备好。下一步："
echo "    make dev   # 后端（终端 1）"
echo "    make web   # 前端（终端 2）"
echo "    或 make all  # 一终端起两边"
echo ""
echo "    访问 http://localhost:3000 → 右上角 ⚙️ 配 LLM"

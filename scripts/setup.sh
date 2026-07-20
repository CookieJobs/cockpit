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

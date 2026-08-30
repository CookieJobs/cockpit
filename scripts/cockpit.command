#!/usr/bin/env bash
# cockpit.command — Double-clickable launcher (macOS)
#
# 一点击 → macOS 自动开一个 Terminal → 在里面跑 `make all` → 前后端都起
# Ctrl+C 干净退出两个服务
#
# 行为:
#   - 同一个 Terminal 窗口 (macOS 双击 .command 自动开的那个)
#   - 不开第二个 Terminal, 不用 iTerm2 检测, 不用 osascript
#   - 自动 cd 到项目目录, 跑 `make all` (调 scripts/dev-all.sh)
#   - 颜色区分: 后端蓝、前端绿
#
# 首次使用注意 (macOS Gatekeeper):
#   - 第一次双击会弹 "无法打开, 因为它来自身份不明的开发者"
#   - 右键 → 打开 → 确认打开 即可
#   - 之后双击就直接运行
#
# 自定义:
#   - 移动项目: 改下面 PROJECT_DIR
#   - 想后台跑: 改 make all 为 make all &
#
# 来源: scripts/cockpit.command (git 追踪), 桌面副本是 cp 出来的,
#       改完想同步: cp scripts/cockpit.command ~/Desktop/cockpit.command

set -euo pipefail

# === 配置: 改这里 ===
PROJECT_DIR="$HOME/Documents/myCraft/cockpit"

# 设 Terminal 窗口标题为 "Cockpit Dev" (区分多个 Terminal 时好认)
echo -ne "\033]0;Cockpit Dev\007"

# === 健康检查 ===
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ 项目不在 $PROJECT_DIR"
    echo "   改这个脚本顶部的 PROJECT_DIR"
    read -r -p "按 Enter 关闭..."
    exit 1
fi

if [ ! -d "$PROJECT_DIR/.venv" ] || [ ! -d "$PROJECT_DIR/web/node_modules" ]; then
    echo "⚠️  首次启动? 开一个普通 Terminal 跑:"
    echo "    cd $PROJECT_DIR && make setup"
    read -r -p "按 Enter 关闭..."
    exit 1
fi

# === 启动: 就在这个 Terminal 跑 ===
cd "$PROJECT_DIR"
clear
make all

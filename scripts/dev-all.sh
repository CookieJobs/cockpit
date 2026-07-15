#!/usr/bin/env bash
# 一个终端同时跑后端 + 前端，颜色区分输出。
# 任一进程退出 → 另一个也一起关，Ctrl+C 干净退出。
set -euo pipefail

cd "$(dirname "$0")/.."

# 颜色
BLUE='\033[1;34m'    # 后端
GREEN='\033[1;32m'   # 前端
YELLOW='\033[1;33m'  # 系统消息
NC='\033[0m'

# 环境检查
if [ ! -d ".venv" ] || [ ! -d "web/node_modules" ]; then
  echo -e "${YELLOW}==> 首次启动？先跑 make setup${NC}"
  exit 1
fi

# 关闭函数：kill 整个进程组。守卫防重入（多个信号会触发多次 trap）
_CLEANED=0
cleanup() {
  if [ "$_CLEANED" -eq 1 ]; then return; fi
  _CLEANED=1
  echo ""
  echo -e "${YELLOW}==> 关闭 dev 服务...${NC}"
  kill 0 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 启动后端（蓝色前缀）
.venv/bin/uvicorn app.main:app --reload --port 7842 2>&1 \
  | sed "s|^|$(printf "${BLUE}[backend]${NC} ")|" &
BACKEND_PID=$!

# 启动前端（绿色前缀）
(cd web && npm run dev 2>&1) \
  | sed "s|^|$(printf "${GREEN}[frontend]${NC} ")|" &
FRONTEND_PID=$!

echo -e "${YELLOW}==> Dev 服务启动中...${NC}"
echo -e "    ${BLUE}后端${NC} http://localhost:7842/docs"
echo -e "    ${GREEN}前端${NC} http://localhost:3000"
echo -e "    ${YELLOW}Ctrl+C 关闭${NC}"
echo ""

# 等任一进程退出 → 自动 kill 另一个
while kill -0 $BACKEND_PID 2>/dev/null && kill -0 $FRONTEND_PID 2>/dev/null; do
  sleep 1
done

if ! kill -0 $BACKEND_PID 2>/dev/null; then
  echo -e "${YELLOW}==> 后端退出，关闭前端${NC}"
fi
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
  echo -e "${YELLOW}==> 前端退出，关闭后端${NC}"
fi
# trap EXIT 会负责 cleanup

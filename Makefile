.PHONY: help setup dev web all stop clean seed-demo

# 默认 target：显示用法
help:
	@echo "Cockpit 启动快捷方式："
	@echo ""
	@echo "  make setup      首次环境准备（venv + pip + npm install + .env）"
	@echo "  make dev        启动后端（http://localhost:7842）"
	@echo "  make web        启动前端（http://localhost:3000）"
	@echo "  make all        一个终端起后端+前端（颜色区分输出）"
	@echo "  make stop       停掉所有 dev 进程"
	@echo "  make clean      清 Python 缓存"
	@echo "  make seed-demo  播种演示数据（清空项目/任务/成就后重置）"
	@echo ""
	@echo "日常：'make dev'（终端 1）+ 'make web'（终端 2）"
	@echo "嫌开两个终端麻烦：'make all'"

setup:
	@./scripts/setup.sh

dev:
	@.venv/bin/uvicorn app.main:app --reload --port 7842

web:
	@cd web && npm run dev

all:
	@./scripts/dev-all.sh

stop:
	-@pkill -f 'uvicorn.*app.main' 2>/dev/null && echo "==> 后端已停"
	-@pkill -f 'next.*dev' 2>/dev/null && echo "==> 前端已停"
	@echo "==> 完成"

clean:
	@find . -type d -name __pycache__ -not -path './.venv/*' -not -path './web/.next/*' -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache
	@echo "==> 缓存已清"

# 播种演示数据（2026-07-20 立）— 体现新做的 6 项特性
# 会清空当前 cockpit.db 里的项目/任务/成就/聊天, 保留 LLM 设置
# 加 --force 跳过确认, --dry-run 只打印不写
seed-demo:
	@.venv/bin/python scripts/seed_demo.py $(filter-out $@,$(MAKECMDGOALS))
	@echo "==> 演示数据就绪"

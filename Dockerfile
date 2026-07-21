# Cockpit 全栈 Docker 镜像 (2026-07-21 立)
#
# 设计原则:
# - 多阶段构建, 镜像只含 Python + 前端 build 产物 (无 node_modules, 无 .next)
# - 前端静态导出 (output: 'export'), FastAPI 启动时接管 web/out/
# - 单端口 7842 同源方案, 避免 CORS / 反代配置麻烦
# - non-root 用户 (cockpit) 跑 uvicorn
# - SQLite 存 /data/cockpit.db, 容器外挂卷持久化

# ===== 阶段 1: 前端 build =====
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# 装依赖 (利用 layer cache — package.json 没变就跳过 npm ci)
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

# 复制前端源码 + 配置
COPY web/ ./

# 静态导出到 out/ 目录
# 关键 (bug fix 2026-07-21): 必须显式注入 NEXT_PUBLIC_API_BASE="" (空字符串) 到 build env.
# 否则本地 web/.env.local 里的 127.0.0.1:7842 会被 inline 进 bundle,
# 部署后前端 fetch 连你本机 7842 (没服务) → "Failed to fetch".
#
# 注: 之前尝试 NEXT_PUBLIC_API_BASE=/api 会出 /api/api/... 双前缀 bug,
# 因为 lib/api.ts 的 request 函数拼路径 `${API_BASE}${path}`, path 本身已含 /api/...
# 修法: build 时注入空字符串, fetch 走相对路径, 浏览器自动拼 origin (同源).
ARG NEXT_PUBLIC_API_BASE=""
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
RUN npm run build

# ===== 阶段 2: Python runtime =====
FROM python:3.12-slim AS runtime

# 防止 .pyc 生成, 防止 stdout 缓冲
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 健康检查 / 调试常用工具
# (curl 给 HEALTHCHECK 用, tini 给 PID 1 信号转发用)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# 创建 non-root 用户
RUN groupadd --system cockpit && \
    useradd --system --gid cockpit --create-home --home-dir /home/cockpit cockpit

WORKDIR /app

# 装 Python 依赖 (利用 layer cache — pyproject.toml 没变就跳过)
COPY pyproject.toml ./
# 用 . 不带 extras: 装核心依赖, 不要 dev 工具 (pytest/ruff/mypy) 也不强求 llm-* extras
# 核心 dependencies 已包含 anthropic + openai (pyproject.toml), 实际够用
# 不带 [all] 是因为 [all] = 核心 + dev + llm-anthropic + llm-ollama + llm-openai
# dev 工具在生产镜像里纯属浪费
RUN pip install --no-cache-dir . 2>&1 | tail -5

# 复制后端代码
COPY app/ ./app/
COPY scripts/ ./scripts/

# 从阶段 1 复制前端 build 产物
COPY --from=frontend-builder /app/web/out ./web/out/

# 数据目录 (容器内, 实际数据通过 volume 挂载到 /data)
RUN mkdir -p /data && chown -R cockpit:cockpit /data /app /home/cockpit

# 切到 non-root
USER cockpit

# 默认环境变量 (部署时用 .env 或 docker-compose env 覆盖)
ENV COCKPIT_ENV=production \
    COCKPIT_HOST=0.0.0.0 \
    COCKPIT_PORT=7842 \
    COCKPIT_DATA_DIR=/data \
    PYTHONPATH=/app

EXPOSE 7842

# 健康检查: /api/health 端点 (FastAPI 自带, 不依赖前端)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:7842/api/health || exit 1

# tini 转发信号, 让 uvicorn 优雅退出
ENTRYPOINT ["/usr/bin/tini", "--"]

# 启动: --proxy-headers 让 FastAPI 知道真实 client IP (如果未来加 nginx 反代)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7842", "--proxy-headers"]

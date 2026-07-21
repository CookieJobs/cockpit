# Cockpit 部署指南 (2026-07-21 立)

## 架构概览

单 Docker 容器 = FastAPI 后端 + Next.js 静态导出前端，单端口 7842 同源访问。

```
┌─────────────────────────────────────┐
│  Browser (你的浏览器)                │
│  http://62.234.180.241:7842         │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Docker container: cockpit          │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │ FastAPI      │  │ StaticFiles │  │
│  │ /api/*       │  │ /, /today,  │  │
│  │ /ws          │  │ /out/*      │  │
│  │ /api/health  │  │ (Next.js)   │  │
│  └──────┬───────┘  └─────────────┘  │
│         │                            │
│         ▼                            │
│  ┌──────────────────────────────┐    │
│  │ SQLite: /data/cockpit.db    │    │
│  └──────────────────────────────┘    │
└────────────┬────────────────────────┘
             │ (volume mount)
             ▼
     /var/lib/docker/volumes/
     cockpit_cockpit_data/_data/cockpit.db
```

## 快速部署 (60 秒)

```bash
# 1. 服务器上 clone 代码
cd /opt  # 或任何你喜欢的目录
git clone https://github.com/CookieJobs/cockpit.git
cd cockpit

# 2. 准备环境变量 (填 LLM API key)
cp deploy/.env.production.example deploy/.env.production
vim deploy/.env.production  # 填 ANTHROPIC_API_KEY 等

# 3. 构建 + 启动
docker compose up -d --build

# 4. 验证
curl http://127.0.0.1:7842/api/health
# 期望: {"status":"ok","version":"0.1.0","name":"Cockpit"}
```

浏览器访问 `http://<服务器IP>:7842` 即可。

## 关键环境变量

`deploy/.env.production` 文件（参考 `.example`）：

| 变量 | 必填 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 推荐 | LLM 主力 key（聊天/任务拆解） |
| `COCKPIT_LLM_BACKEND` | 否 | `anthropic` / `deepseek` / `openai` / `minimax` / `custom`，默认 `anthropic` |
| `COCKPIT_LLM_MODEL` | 否 | 默认 `claude-sonnet-4-5` |
| `COCKPIT_CORS_ORIGINS` | 否 | 默认 `localhost:3000` 同源不触发 CORS，加反代时改这里 |
| `COCKPIT_ENCRYPTION_KEY` | 否 | 32 字节随机串，加密存的 LLM settings，没设也能跑 |

> **没填 LLM key 也能起**，只是聊天/任务拆解会走关键词 fallback（功能降级但 UI 正常）。

## 数据持久化

SQLite 文件在容器内 `/data/cockpit.db`，通过 named volume `cockpit_data` 持久化到宿主机的 Docker volume 目录。

**备份**：
```bash
docker compose cp cockpit:/data/cockpit.db ./backup-$(date +%Y%m%d).db
```

**恢复**：
```bash
docker compose cp ./backup.db cockpit:/data/cockpit.db
docker compose restart cockpit
```

**想换位置**（比如挂到大磁盘）：改 `docker-compose.yml` 的 volume 部分，从 named volume 改成 bind mount：
```yaml
volumes:
  - type: bind
    source: /data/cockpit   # 宿主机路径
    target: /data           # 容器内路径（代码里写死了这个）
```

## 升级

```bash
cd /opt/cockpit
git pull
docker compose up -d --build
```

数据在 volume 里，升级不会丢。

## 端口冲突

如果 7842 已被占用（比如别的服务），改 `docker-compose.yml`：
```yaml
ports:
  - "8080:7842"   # 宿主机 8080 → 容器 7842
```

然后浏览器访问 `http://<IP>:8080`。

## 加 HTTPS / 域名

最稳的方案是套一层 nginx / Caddy 反代：

**Caddy (推荐，自动 HTTPS)**：
```caddyfile
cockpit.yourdomain.com {
    reverse_proxy 127.0.0.1:7842
    encode zstd gzip
}
```

**nginx**：
```nginx
server {
    listen 443 ssl http2;
    server_name cockpit.yourdomain.com;
    # ... ssl 配置 ...

    location / {
        proxy_pass http://127.0.0.1:7842;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;  # LLM 流式响应可能很慢
    }
}
```

⚠️ 加反代后要改 `COCKPIT_CORS_ORIGINS=https://cockpit.yourdomain.com`，否则 fetch 会因 CORS 被浏览器拒。

## 监控

容器自带 healthcheck (`/api/health`)，Docker 自动重启失败容器。

**查日志**：
```bash
docker compose logs -f cockpit
```

**查资源**：
```bash
docker stats cockpit
```

## 故障排查

**容器起不来**：
```bash
docker compose logs cockpit
# 看最后 30 行错误
```

**端口访问不到**：
```bash
# 服务器本地测
curl http://127.0.0.1:7842/api/health
# 防火墙检查
sudo iptables -L -n | grep 7842
sudo firewall-cmd --list-ports  # 如果用 firewalld
```

**数据没了**：
```bash
docker volume inspect cockpit_cockpit_data
# 看 Mountpoint 路径, 直接 ls 那个目录
```

**前端页面空白**：
- 打开浏览器 DevTools 看 Network → 是不是 /api/* 404
- 多半是 CORS 没配（加了反代但忘改 `COCKPIT_CORS_ORIGINS`）

**聊天报 "（无响应）"**：
- 看后端日志 `docker compose logs cockpit | grep -i error`
- 多半是 LLM API key 没填或失效

## 卸载

```bash
# 停服务
docker compose down
# 删数据 (警告: 会清掉所有项目/任务/成就/对话!)
docker volume rm cockpit_cockpit_data
# 删代码
rm -rf /opt/cockpit
```

## 与本地开发的差异

| 项 | 本地 dev | Docker 部署 |
|---|---|---|
| 启动方式 | `make dev` + `make web` | `docker compose up -d` |
| 端口 | 7842 (后端) + 3000 (前端) | 7842 (单端口) |
| CORS | 开发用 (3000 ↔ 7842) | 同源，不需要 |
| 数据目录 | `~/.cockpit/cockpit.db` | `/data/cockpit.db` (Docker volume) |
| 改代码 | 即时生效 | 重新 `docker compose up -d --build` |
| LLM key | `.env` 文件 | `deploy/.env.production` 文件 |

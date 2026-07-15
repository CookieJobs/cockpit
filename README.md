# Cockpit

> Local-first personal agent that captures what you do, turns completed work into reusable achievements, and helps you write weekly reports and 述职 materials — powered by your own LLM API key, with your data staying on your own machine.

> 你的个人项目驾驶舱——不替你干活，替你记住你干过什么、要干什么。

Cockpit 是一个给互联网产品/运营/技术人员的"工作流记忆外挂"。用对话式 agent 帮你记录任务、完成时沉淀成就，季度述职前不再抓瞎。

> 📦 GitHub: [CookieJobs/cockpit](https://github.com/CookieJobs/cockpit)

## 核心特性

- **完成即沉淀** — 任务做完不是消失了，而是沉淀成成就资产，越用越值钱
- **本地优先** — 默认数据存本机 SQLite，隐私可控
- **AI 主动执行** — 自然语言直接建项目/任务，agent 自己拆解、自己动手，不等用户说"创建"
- **多 LLM 后端** — 支持 Anthropic Claude / DeepSeek / MiniMax / 自定义 OpenAI 兼容端点
- **多端配置** — 运行时通过 Web UI 配 API key，不用改 .env
- **中文场景深耕** — 中文 prompt / 中文工具描述 / 飞书/钉钉生态适配
- **单人独立工具** — 专注"个人项目管理"，不抢团队协作

## 状态

✅ **v0.2 MVP** — 核心功能完成，可日常使用：

- [x] 项目 / 任务 / 成就 CRUD
- [x] FastAPI 后端 + Next.js 15 前端
- [x] SQLAlchemy 2.0 async + aiosqlite
- [x] LLM 集成 + function calling（14 工具）
- [x] Markdown tool call fallback（弱模型兼容）
- [x] 多 session 聊天历史持久化
- [x] 5 个 LLM 后端（Anthropic / DeepSeek / MiniMax / OpenAI / Custom）
- [x] Web UI 配 LLM（DB 优先，.env fallback）
- [x] 任务 inline 编辑（priority / due / description）
- [x] 项目删除 + task 删除

## 项目结构

```
cockpit/
├── app/                    # FastAPI 后端
│   ├── core/               # 业务核心（数据模型 + 存储 + 排序）
│   │   ├── models.py
│   │   ├── storage.py
│   │   ├── focus.py
│   │   └── chat.py         # LLM dispatch + 关键词 fallback
│   ├── api/                # API 路由
│   │   ├── projects.py
│   │   ├── tasks.py
│   │   ├── achievements.py
│   │   ├── chat.py
│   │   ├── chat_sessions.py
│   │   ├── llm.py
│   │   └── llm_settings.py
│   ├── llm/                # LLM 集成
│   │   ├── base.py         # LLMClient 抽象
│   │   ├── anthropic.py
│   │   ├── openai.py       # OpenAI 兼容（DeepSeek / MiniMax / Ollama-removed）
│   │   ├── router.py       # DB-priority config
│   │   ├── tools.py        # 14 个 function-calling 工具
│   │   └── chat_engine.py  # 多轮 tool-calling + markdown fallback
│   └── tests/              # 单元测试（66 tests）
├── web/                    # Next.js 15 前端
│   ├── app/                # App Router
│   ├── components/         # MainBoard / ChatWindow / Markdown
│   └── lib/api.ts          # API client
├── scripts/                # 启动辅助脚本
│   ├── setup.sh            # make setup 背后的幂等环境准备
│   └── dev-all.sh          # make all 背后的一终端双服务脚本
├── docs/
│   ├── PRD.md              # 产品需求文档
│   └── ...
├── Makefile                # make setup / dev / web / all / stop
├── pyproject.toml
├── README.md
└── LICENSE
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+（前端）
- macOS / Linux

### 一键启动（推荐）

```bash
cd cockpit
make setup   # 首次：venv + pip + npm install + .env（幂等，跑过就跳过）
```

`make setup` 跑完后，挑一个日常用法：

**选项 A：两个终端分开**（前后端日志独立显示，看日志更清楚）

```bash
make dev   # 终端 1：后端 http://localhost:7842
make web   # 终端 2：前端 http://localhost:3000
```

**选项 B：一个终端搞定**（颜色区分后端/前端输出，任一挂掉自动关另一个）

```bash
make all
```

打开 <http://localhost:3000>，右上角 ⚙ 设置 → 选 LLM 后端 → 填 key → 测试 → 保存。配置存在本地 db，重启不丢。

### 常用命令

```bash
make          # 查看所有命令
make stop     # 停掉所有 dev 进程
make clean    # 清 Python 缓存
```

### 手动启动（备选）

不想用 Makefile 也可以手动：

```bash
# 后端
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env 至少填一个 LLM API key（也可跳过，去 Web UI 配）
uvicorn app.main:app --reload --port 7842

# 前端（另一个终端）
cd web
npm install
npm run dev
# 访问 http://localhost:3000
```

### 测试

```bash
# 后端测试（66 tests）
pytest app/tests/ -v

# 前端类型检查
cd web && npx tsc --noEmit
```

## LLM 后端

5 个后端，全部支持自定义 API key + base URL：

| 后端 | 适用 | 备注 |
|---|---|---|
| Anthropic | Claude Sonnet / Opus | 工具调用最稳 |
| DeepSeek | deepseek-v4-flash / v4-pro | 国产，便宜，1M 上下文 |
| MiniMax | MiniMax-M3 | 国产，1M 上下文 / Coding & Agent 强 |
| OpenAI | GPT-4o / 月之暗面 / 其他 | OpenAI 兼容 |
| Custom | 自定义 | 完全自定义 base URL + model |

UI 配 LLM：右上角 ⚙ 设置 → 选后端 → 填 key → 测试 → 保存。配置存在本地 db，重启不丢。

> **使用 DeepSeek R1 / MiniMax M3 等推理模型时注意**：模型在 `content` 字段会写 `<think>...</think>` CoT 块，已在后端 `chat_engine.strip_think_blocks` + 前端 `ChatWindow.stripThinkBlocks` 双重剥离，不用担心。

## 数据存储

- SQLite 数据库：`~/.cockpit/cockpit.db`（macOS/Linux）
- LLM 配置：DB `settings` 表（key-value）
- 项目 / 任务 / 成就：DB `projects` / `tasks` / `achievements` 表
- 聊天历史：DB `chat_sessions` / `chat_messages` 表

完全本地，无云同步，隐私可控。

## 开发

```bash
# 推荐：Makefile 启服务（见上文"一键启动"）
make dev    # 后端
make web    # 前端
make all    # 一终端起两边

# 测试
pytest app/tests/            # 后端
cd web && npx tsc --noEmit   # 前端类型
make clean                   # 清 Python 缓存
```

改 Python 代码不生效时，先 `make clean` 或 `rm -rf app/llm/__pycache__` 再重启 uvicorn。

## 文档

- 📄 [产品需求文档 (PRD)](./docs/PRD.md)
- 📄 [设计文档](./docs/design.md)（如有）

## 相关项目

- 🛠️ [task-cockpit](https://github.com/CookieJobs/task-cockpit) — 同名 skill 仓库，给 Claude Code / Cursor 等 agent 用，与本产品形态不同、用户不同，独立维护

## 许可证

MIT

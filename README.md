# 拾光 (Shiguang)

> 你的个人项目驾驶舱——不替你干活，替你记住你干过什么、要干什么。

拾光是一个给互联网产品/运营/技术人员的"工作流记忆外挂"。用对话式 agent 帮你记录任务、完成时沉淀成就，季度述职前不再抓瞎。

## 核心特性

- **完成即沉淀** — 任务做完不是消失了，而是沉淀成成就资产，越用越值钱
- **本地优先** — 默认数据存本机，隐私可控
- **中文场景深耕** — 对接飞书/钉钉/微信生态
- **单人独立工具** — 专注"个人项目管理"，不抢团队协作

## 状态

🚧 **v0.1 内部开发中** — 当前处于 Week 1-2 基础架构搭建阶段。

## 项目结构

```
拾光/
├── app/                # FastAPI 后端
│   ├── core/           # 业务核心（数据模型 + 存储 + 排序）
│   ├── api/            # API 路由
│   ├── llm/            # LLM 集成（Anthropic + Ollama）
│   └── tests/          # 单元测试
├── web/                # Next.js 前端（待搭建）
├── docs/               # 设计文档
│   ├── PRD.md          # 产品需求文档
│   ├── design.md       # 技术设计
│   └── api.md          # API 文档
├── scripts/            # 工具脚本
├── pyproject.toml
└── README.md
```

## 文档

- 📄 [产品需求文档 (PRD)](./docs/PRD.md)
- 🔧 技术设计（待写）
- 📚 API 文档（开发中）

## 相关项目

- 🛠️ [task-cockpit](https://github.com/CookieJobs/task-cockpit) — 同名 skill 仓库，给 OpenClaw / Claude Code / Cursor 的 SKILL.md 用户使用，与本产品形态不同、用户不同，独立维护

## 开发

```bash
# 安装依赖（待实现）
pip install -e ".[dev]"

# 运行测试（待实现）
pytest

# 启动后端（待实现）
uvicorn app.main:app --reload --port 7842
```

## 许可证

TBD

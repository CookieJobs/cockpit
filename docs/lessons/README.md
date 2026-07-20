# Cockpit Lessons — 踩过的坑索引

> 给后面接手 / 跨时间回看的 agent 用。每个 lesson 是"症状 + 根因 + 教训 + 修法位置"。

## 目录

按主题分文件（2026-07-20 立）：

| 文件 | 主题 | Lessons |
|---|---|---|
| [01-frontend-ux-bugs.md](./01-frontend-ux-bugs.md) | 前端 UX 状态机 / 视觉编码 | #1 TaskRow 二次确认 bug · #4 状态机堵死完成路径 · #5 "低"优先级色点不可见 |
| [02-llm-pitfalls.md](./02-llm-pitfalls.md) | LLM 集成坑 | #2 CoT 暴露 + markdown fallback 误执行 |
| [03-fastapi-and-tooling.md](./03-fastapi-and-tooling.md) | 后端 / 工具链 | #3 FastAPI simple type 参数 body 丢失 · #7 `make setup` 引导歧义 · #8 Python 3.11 + greenlet 双重坑 |
| [04-testing-strategy.md](./04-testing-strategy.md) | 测试方法论 | #6 端到端 UX 路径静态分析测试 |

## 使用方式

1. 接手项目时**先读这个索引**, 知道有这些坑
2. 改相关模块前, 点开对应文件, 看 lessons 里的"修法位置"定位代码
3. 修法要 commit 完顺手在对应文件追加"踩坑记录" — 这是这份 AGENTS.md 系统的复利

## 与 AGENTS.md 主文件的关系

- **AGENTS.md**（项目根）保留：项目一句话、核心路径、LLM 后端约定、测试入口、设计哲学、Changelog
- **本目录**保留：每个具体 bug 的完整复盘 (症状/根因/教训/修法位置)
- 拆分动机：AGENTS.md 涨到 20KB+ 时, 入口可读性下降, lessons 细节按主题下沉更易维护

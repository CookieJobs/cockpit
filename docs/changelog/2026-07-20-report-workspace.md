---
date: 2026-07-20
slug: report-workspace
title: 兑现 #1 周报/述职 workspace + 4 项 UX 升级
status: 现行
supersedes: —
related_lessons: —
---

## Changelog：2026-07-20 兑现 #1 周报/述职 workspace + 4 项 UX 升级

兑现上次对话（"看一下这个项目然后说一下有什么新想法"）批准的方向：

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **周报/述职 workspace** | `web/app/report/page.tsx` + `web/lib/templates.ts` | 时间范围 × 模板, 左侧升级入口, 右侧 markdown 草稿 + 复制/下载 .md |
| 3 | `cvStatus` 三态 (ready / needs_data / pending) | `app/core/models.py` + CompleteTaskModal + achievements 页 | 述职升级路径中间态, 成就库按状态过滤 |
| 4a | **项目归档 UI** | `web/components/MainBoard.tsx` ProjectCard / ProjectsSection | Archive 按钮 + "已归档 N"开关 + 恢复 |
| 4b | **ChatWindow 重构** | `web/lib/hooks/useChatStream.ts` | 869 → 776 行, 流式状态机抽到独立 hook, 6 个不变量测试锁住 |
| 4c | **`/today` 晨间 ritual** | `web/app/today/page.tsx` | 大日期 + greeting + focus 5 + 完成 button + 已完成折叠 |
| 4d | **AGENTS.md 拆 lessons** | `docs/lessons/{01..04}-*.md` | 275 → 141 行, 按主题分文件, 主页只放索引 |

**回归**：84 → **108** tests pass（+24: cvStatus 模型/存储/API/UI + 3 组新不变量测试锁住 UI 入口）

> Lessons #5-#8 完整内容已迁移到 [`docs/lessons/`](./docs/lessons/README.md), 这里不重复。


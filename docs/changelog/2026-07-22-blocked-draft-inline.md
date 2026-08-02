---
date: 2026-07-22
slug: blocked-draft-inline
title: blocked / draft inline edit (Agent 字段人手可改)
status: 现行
supersedes: —
related_lessons: —
---

## Changelog：2026-07-22 blocked / draft inline edit (Agent 字段人手可改)

用户原则: **"凡是 Agent 可以操作的字段, 人也可以操作"** — 之前的缺口是 `blocked` / `draft` 两个字段 Agent 能改 (通过 `tool_update_task`) 但前端没手动入口。

### 现状扫描 (扫之前)

Agent 工具能改的 task 字段 (`app/llm/tools.py:139-175 tool_update_task`):
- `title` / `description` / `priority` / `due` / `status` / `checklist` — UI 都已有 inline edit
- **`blocked` / `draft` — UI 无入口** (本次补)

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu 末尾加 blocked / draft 双方向 toggle** | `web/components/MainBoard.tsx` StatusMenu | 紧跟"完成 ✨" 项, 分隔线 + 🚧 阻塞 / 📝 草稿 两行 toggle |
| 2 | **TaskRow 加 updateField 通用函数** | TaskRow | 跟 updatePriority / updateDue 同款 PATCH + onChange() 流程, 走 api.updateTask 不做乐观更新 |
| 3 | **StatusMenu 接收 blocked / draft / onToggleBlocked / onToggleDraft 4 prop** | StatusMenu 函数签名 | 保持"一个 popover 管所有 task 状态/标签切换" 的 UX 一致性 |
| 4 | **不变量测试 4 条新增** | `app/tests/test_complete_path_invariants.py` | #13 StatusMenu 必须有 statusmenu-toggle-blocked / statusmenu-toggle-draft 按钮 + 动态文案 + emoji; #14 TaskRow 必须透传 4 prop; #15 updateField 通用函数必须有 |
| 5 | **端点级 PATCH 回归测试 5 条** | `app/tests/test_api_task_patch_inline_edit.py` (新文件) | blocked true/false + draft true/false + 字段独立 — 锁住 PATCH 端点真解析 body, 不被 FastAPI 静默吞 |

### 设计决定记录

- **StatusMenu 末尾加 toggle, 不在第二行 meta 徽章加 click**:
  - 单一入口原则 — 一个 popover 管所有 task 状态/标签切换, 用户认知一致
  - meta 徽章 (`MainBoard.tsx:1089-1093`) 保持纯展示 (视觉提示), 避免双入口导致"哪个更优先" 困惑
  - 跟现有"完成 ✨" 同位同节奏 — 状态项 / 完成项 / toggle 项 都是 popover 内的"动作型" 项
- **toggle 走 PATCH + onChange, 不做乐观更新**:
  - 跟 StatusMenu 状态切 / PriorityMenu 优先级切 / DueEditor due 改完全一致
  - SWR revalidate 后所有看板视图同步, 不需要乐观更新
  - 失败回滚: SWR 本身有 mutate-on-error, PATCH 失败用户看到的就是原状态
- **toggle 文案"标记 / 解除" 而非 checkbox 形态**:
  - checkbox 形态 (`✓ 阻塞` toggle) 跟状态项"当前" 标识视觉撞
  - "标记阻塞" / "解除阻塞" 明确动作方向, 跟"完成 ✨" 的"动作+提示" 风格一致
- **emoji 跟 meta 徽章对齐**:
  - 阻塞: 🚧 (跟 MainBoard.tsx:320 `item.blocked ? "🚧" : "○"` 同一 emoji, 用户视觉联想不断)
  - 草稿: 📝 (新 emoji, 但跟"待确认" 语义自然配对)
- **后端 schema 早就有 blocked / draft, 零后端改动**:
  - `TaskUpdate` schema (app/core/models.py:232-233) 早就允许 `blocked: Optional[bool]` 和 `draft: Optional[bool]`
  - storage.update_task 早就支持 (test_storage.py:129, 151, 152 都有覆盖)
  - 缺的**只是**前端手动入口 — 纯 UX 补丁, 不动后端架构

### 字段表 (扫完之后)

| task 字段 | Agent 改 | UI 改 | 入口 |
|----------|----------|------|------|
| `title` | ✅ | ✅ | 双击 inline edit |
| `description` | ✅ | ✅ | 展开区 textarea |
| `priority` | ✅ | ✅ | 第一行色点 PriorityMenu |
| `due` | ✅ | ✅ | 第一行右侧 DueEditor |
| `status` | ✅ | ✅ | 第一行色点 StatusMenu |
| `checklist` | ✅ | ✅ | 展开区行内增删勾 |
| `blocked` | ✅ | ✅ **(新)** | StatusMenu 末尾 🚧 toggle |
| `draft` | ✅ | ✅ **(新)** | StatusMenu 末尾 📝 toggle |

**回归**：132 → **141** tests pass (+9: 5 个端点级 PATCH 回归 + 4 个 UI 静态不变量)


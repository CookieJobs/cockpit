---
date: 2026-07-17
slug: status-menu-v2
title: StatusMenu 状态菜单化 v2
status: **被 v3 推翻**
supersedes: —
related_lessons: #11, #12
---

## Changelog：2026-07-17 状态菜单化 v2 (已被 2026-07-21 v3 推翻部分)

> ⚠️ **2026-07-21 v3 推翻**: "整行 click = 完成 modal" 决策被推翻 (见下方 Changelog v3)。
> 整行 90% 是空白, 空白点中也算"用户操作" 触发完成 modal → 用户报"红框空白点中不该触发"。
> 改为 task-cockpit 原版: 整行 click = 展开/收起, 完成走 2 个显式入口 (StatusMenu popover + hover ✅ 按钮)。

**背景**: Round 1 的 cycleStatus (○ ↔ ◐ 单字符循环) 用户嫌"○◐ 状态按钮不好",
信息密度低 + 字符对用户不熟 + 跟 PriorityMenu 下拉风格不一致。

**v2 方案** (commit 00e3148, 已部分回退):

- `StatusMenu` 组件 (MainBoard.tsx, 跟 PriorityMenu 同结构)
  - 触发按钮: 色点 + 状态文字 + ⌄ 箭头 (色点 + 文字 双编码, 不用记符号)
  - 下拉 3 行:
    - ○ 未开始 (当前项高亮 accent, 立刻 PATCH status)
    - ◐ 进行中 (当前项高亮 accent, 立刻 PATCH status)
    - ───── (分隔)
    - ✅ 完成 ✨ (弹 4 字段 modal, 不直接切 status)
  - click outside / Esc 关闭, Tab focus + Enter/Space 打开 (基础可达性)

- **删 cycleStatus 函数 + Play "开始" 按钮** (状态切换入口并入下拉, 视觉去重)
- ~~**整行 click 保持** = 完成 modal~~ (v3 已推翻, 改 toggleExpand)
- ~~**hover ✅ 按钮**: 删了 (跟整行 click 重复)~~ (v3 加回, 这次不重复)

**为什么不直接 PATCH status="已完成"**:
- 已沉淀的 task 在 storage 层**已被删除** (storage.complete_task 先写 achievement 再删 task)
- 所以"已完成"状态在看板运行时**永远不可达**
- 下拉里放"已完成" 选项会误导用户: 选了之后弹了 modal 不是"切状态"
- 改成显式"完成 ✨" 项, 视觉明确"这一项会弹窗"


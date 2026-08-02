---
date: 2026-07-22
slug: status-menu-fused
title: StatusMenu 状态融合 + 移到右侧 + 第二行徽章删除 (v3)
status: 现行
supersedes: v2
related_lessons: —
---

## Changelog: 2026-07-22 StatusMenu 状态融合 + 移到右侧 + 第二行徽章删除 (v3)

用户反馈: 「任务状态组件跟优先级色点堆在左侧, 跟优先级有点重复的感觉」 + 「进行中用一个横条, 阻塞用另一个徽章, 这两个其实是同一维度信息, 应该融合成一个组件」。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu trigger 改"融合形态"** | `web/components/MainBoard.tsx` StatusMenu | 同一 button 多形态: 阻塞 → 🚧 warning, 草稿 → 📝 accent, 否则 → 短进度条 (16x4 跟 status 长度)。优先级: 阻塞 > 草稿 > 状态 |
| 2 | **StatusMenu 从左侧挪到右侧** | TaskRow 第一行 JSX | 新顺序: PriorityMenu (左) → 标题 → StatusMenu (右) → DueEditor (更右)。StatusMenu 跟 due 形成"右栏", 用户从右到左扫: 状态+阻塞/草稿 → due → 展开 → hover 按钮 |
| 3 | **第二行 meta 删掉"草稿/阻塞"徽章** | TaskRow 第二行 meta | 上移到第一行右侧状态指示器后, 第二行不再需要重复表达。meta 条件从 `(task.draft \|\| task.blocked \|\| ...)` 改成 `(totalCount > 0 \|\| taskAgeDays >= 2)`, 只剩 checklist 进度 + "挂了 N 天" 提示 |
| 4 | **不变量测试 3 条新增/改写** | `app/tests/test_complete_path_invariants.py` | #8 改写: `test_statusmenu_trigger_is_fused_form` 锁住"同一 button 多形态" (blocked/draft 分支 + 无修饰横条 fallback + 无状态文字/ChevronDown); #8b 新: `test_statusmenu_is_in_right_side_of_taskrow` 锁住右侧位置 (PriorityMenu < StatusMenu < DueEditor 索引顺序); #8c 新: `test_taskrow_meta_row_no_draft_blocked_badges` 锁住第二行无徽章 (无 `{task.draft &&` / `{task.blocked &&` / 草稿阻塞背景 class) |
| 5 | **title 增强** | StatusMenu trigger `title` 属性 | 从 `状态: ${status} (点击切换)` 改成 `状态: ${status}${blocked ? " · 阻塞" : ""}${draft ? " · 草稿" : ""} (点击切换)`, hover 能看到完整修饰 |

### 设计决定记录

- **融合优于并行**:
  - 旧版: 进行中 (横条) 在第一行左侧, 阻塞 (🚧 徽章) 在第二行 — 同一维度信息分散在两行, 用两种视觉语言表达
  - 新版: 同一位置同一组件, 形态切换 — 视觉更紧凑, 状态判断只扫一处
- **优先级: 阻塞 > 草稿 > 状态**:
  - 阻塞 = 任务被外部依赖卡住, 必须先解决阻塞才能推进 → 视觉优先级最高
  - 草稿 = 待确认, 优先级中等
  - 状态 (进行中/未开始) = 基础信息, 优先级最低
  - 三者冲突时按这个顺序覆盖
- **第二行徽章全删, 不保留冗余**:
  - 保留 = 同一信息出现在两行, 视觉重复
  - 用户已经能看到第一行右侧 🚧/📝, 第二行再显示一次是噪音不是信号
  - 教训: 信息一致性强 > 信息密度高
- **StatusMenu trigger 保持 w-5 h-5 button 尺寸**:
  - 阻塞/草稿状态下渲染 13px emoji, 居中显示在 20x20 容器里 — 视觉权重跟横条形态接近, 切换不突兀
  - 不放大 button 尺寸 = 保持"右栏"密度, 不破坏 due / 展开指示器 / hover 按钮 的位置
- **不变量 8 改写而非新增**:
  - 旧不变量 8 (test_statusmenu_trigger_is_pure_dot_no_text_no_chevron) 的核心约束 — "trigger button 不能有 status 文字 / ChevronDown" — 仍然成立 (回归保护)
  - 但 "必须有 w-4 h-1 横条" 改为 "必须有 blocked 分支 + draft 分支 + 无修饰横条 fallback" — 更精确地反映"融合形态" 设计

### StatusMenu v2 → v3 决策对比

| 版本 | 形态 | 阻塞/草稿表达 | 跟 PriorityMenu 区分度 | 跟 due 配合 | 用户反馈 |
|---|---|---|---|---|---|
| v2 (2026-07-22) | 16x4 横条 (无修饰) | 第二行独立徽章 (🚧 阻塞 / 📝 草稿) | ✅ 圆 vs 矩形 | ❌ 一个左一个右 | "分散在两行, 同一信息两种表达" |
| v3 (本次) | 同一 button 多形态 (🚧/📝/横条) | 同一组件内覆盖表达 | ✅ 圆 vs 矩形 + 同位置切换 | ✅ StatusMenu 挪到 due 左边, 形成右栏 | 待验证 (刚交付) |

**回归**: 141 → **160** tests pass (+19: 3 个新不变量测试 [1 改写 + 2 新增] + 16 个端点级 + 集成测试同步). `tsc --noEmit` 0 错误.


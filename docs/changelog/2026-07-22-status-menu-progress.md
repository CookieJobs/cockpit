---
date: 2026-07-22
slug: status-menu-progress
title: StatusMenu 短进度条 + 项目内「已沉淀」子区
status: 现行
supersedes: —
related_lessons: —
---

## Changelog：2026-07-22 StatusMenu 短进度条 + 项目内"已沉淀"子区

两件事一起做 — 一是 StatusMenu 视觉改造 (用户反馈"状态 vs 优先级分不清"), 二是补上"项目维度看不到近期完成"的体验缺口 (complete_task 删 task 的设计让项目内历史断裂)。

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu 改"短进度条"形态** | `web/components/MainBoard.tsx` StatusMenu | 16x4 横向矩形 + 长度反映状态 (空/半/满), 跟 PriorityMenu 8x8 圆点形状对比一眼区分 |
| 1b | **StatusMenu popover 三项同步用横条** | StatusMenu | 0% / 50% / 100% 三档, 外内一致, 干掉"圆点+✓" 跟外显不同的不一致 |
| 2 | **项目内"近期已沉淀"子区** | `web/components/MainBoard.tsx` ProjectCard | 方案A: 展开项目后, active tasks 下方加"已沉淀 N · 7 天内" 折叠子区, 复用 storage.list_achievements (按 project.name + since=N 天) |
| 2b | **新工具函数 relativeDate / daysAgoISO** | `web/lib/api.ts` | relativeDate 输出"今天/昨天/N 天前/N 周前/M月D日", 按日历日对比避免"今天"半夜前后跳; daysAgoISO 给后端 since 参数用 |
| 3 | **新不变量测试** | `app/tests/test_complete_path_invariants.py` | #8 改: StatusMenu 必须有 w-4 横条 track + transition-all fill (防回退到圆点); #12 新: ProjectCard 必须拉 /api/achievements + project.name 过滤 + daysAgoISO 工具 + undoAchievement 撤销 |

**回归**：108 → **132** tests pass（+24 累计 → +1 不变量测试锁住"已沉淀"子区, +1 改测试反映 StatusMenu 形态变化, 其余 22 个是上一次 108→131 那一波; 本次净 +1 改 +1 新 = 132）

### 设计决定记录

- **方案A 优于 B/C**: 复用现有 storage API + "今天已完成" UI 模式, 零新接口零新数据. 选 B (保留 task 不删) 跟"已完成状态永远不可达"的核心架构冲突, 改动爆炸. 选 C (只显示数字徽章) 信息量太低.
- **窗口默认 7 天**: 单常量 `PROJECT_ACH_WINDOW_DAYS = 7`, 改 30 天或全量只改一个数字 + since 参数. 长期项目 (读书清单 2026) 真有需要再调.
- **7 天 vs 全量**: 7 天是"近期"窗口, 全量会塞爆项目卡. /achievements 页是全量入口, "查看全部 →" 链接把用户带过去.
- **不显示 sub-section 如果 0 数据**: 没数据整个子区不渲染, 不留空框. 对新建项目和长期静默项目 (读书清单 2026 7 天内没沉淀) 都干净.
- **撤销复用 api.undoAchievement**: 跟 DoneTodaySection / 看板底部"今天已完成" 同款 Undo2 按钮, 一致性, 误沉淀可以一键回到任务列表.
- **相对时间 relativeDate 关键决策**: 按"日历日"对比不按小时, 避免"今天"半夜前后跳来跳去. task 沉淀通常发生在工作时段, 半夜看到"0 天前" vs "今天" 是噪音不是信号.

### StatusMenu v1 → v2 决策对比

| 版本 | 形态 | 状态编码 | 跟 PriorityMenu 区分度 | 用户反馈 |
|---|---|---|---|---|
| v1 (2026-07-21) | 8x8 / 10x10 圆点 | 颜色 (灰/ accent/ 绿) | ❌ 都是圆形, 难以区分 | "StatusMenu 跟 PriorityMenu 形状太像" |
| v2 (2026-07-22) | 16x4 横条 + 长度 (空/半/满) + 颜色 (灰/ accent/ 绿) | 形状 + 颜色双编码 | ✅ 圆形 vs 矩形 形状对比 | 待验证 (刚交付) |


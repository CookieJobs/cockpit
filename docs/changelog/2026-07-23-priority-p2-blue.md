---
date: 2026-07-23
slug: priority-p2-blue
title: P2 换冷色蓝 (跟 P1 暖色撞色修复)
status: 现行
supersedes: —
related_lessons: —
---

## Changelog: 2026-07-23 P2 换冷色蓝 (跟 P1 暖色撞色修复)

用户反馈: "P1 跟 P2 两个优先级的组件的颜色非常的接近, 我希望你能够给它换一下颜色,能够让两个很快的区分开。"

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **加 `info` 色** | `web/tailwind.config.ts` | `#3b82f6` (Tailwind blue-500), 跟 danger / warning / accent / success 同级 |
| 2 | **P2 badge 改 info 蓝** | `web/lib/api.ts` `PRIORITY_BADGE_STYLES` | `bg-info/15 text-info border-info/30`, 共享给 MainBoard PriorityMenu + /today FocusRow |
| 3 | **P2 左侧色条改 info 蓝** | `web/lib/api.ts` `PRIORITY_BAR_STYLES` (新立) | `bg-info`, FocusItem 左侧 3px 竖条用 |
| 4 | **/today FocusRow 同步** | `web/app/today/page.tsx` | 跟 MainBoard 共享 `PRIORITY_BADGE_STYLES` / `PRIORITY_BAR_STYLES`, 改色只改一处 |
| 5 | **不变量测试同步** | `app/tests/test_complete_path_invariants.py` | `test_priority_badge_styles_4_levels` 期望 P2 从 `bg-accent/15 text-accent` 改 `bg-info/15 text-info` |

### 设计决定记录

- **色环跨越 ~200° (红 0° → 橙 30° → 蓝 220°) 优于 同色系微调**:
  - 旧版: 红 0° → 橙 30° → 琥珀 45° — P1/P2 只差 15° 肉眼分不出
  - 新版: 红 0° → 橙 30° → 蓝 220° — P1/P2 跨冷暖, 一眼区分
  - 经验: 同一色相不同明度 (橙 vs 琥珀) 看起来"差不多", 跨色相才能拉开
- **蓝色 (info) 优于其他冷色**:
  - 绿 = success, 跟"完成" 概念撞, 排除
  - 紫/品红 = 警告感, 跟 P0 红冲突
  - 蓝 = 中性"信息" 蓝, 设计系统通用约定, 跟红/橙对比最强
  - `#3b82f6` (blue-500) 是 Tailwind 蓝调中段, dark mode 下 `#15 / #30` opacity 底色 + 边框都清晰
- **P2 = 蓝意外地解决跟 StatusMenu 视觉混淆**:
  - 旧版 P2 用 accent (琥珀) = StatusMenu "进行中" 同色 — 优先级普通态跟状态进行中色一样, 视觉上像在说"进行中"
  - 新版 P2 用 info (蓝) — 普通优先级是中性默认态, 蓝色最不抢眼, 也跟"进行中" 完全区分
- **PRIORITY_BAR_STYLES 独立常量 而非合并到 BADGE**:
  - 优先级左侧竖条 vs badge 用不同 opacity 体系:
    - BADGE: 软底色 (color/15) + 同色描边 (color/30) + 同色文字 — 多信息密度
    - BAR: full opacity 单色 — 最快视觉信号
  - 合并会让一边用不到, 也违背 single responsibility — 改色梯度要同时调两套, 容易漏
  - 但**值是同步的** (P2 都是 info), 只在 tailwind 类层面不同
- **共享给 /today 不冗余**:
  - 旧版 MainBoard 和 /today 各自硬编码 `=== "P0" ? "bg-danger" : ...`, 改色要改两处
  - 新版 `PRIORITY_BAR_STYLES` / `PRIORITY_BADGE_STYLES` 从 lib/api.ts 单点 export, 两边 import 同一份
  - lesson: 颜色/样式常量跟类型一起放在 lib/api.ts, 是这个项目已经形成的约定 (跟 `statusIcon` / `dueColor` 同一档)

### 颜色梯度对照 (P0/P1/P2/P3)

| 档 | 色名 | hex | 色环 hue | 跟上一档 hue 差 | 紧急度语义 |
|---|---|---|---|---|---|
| P0 | danger (红) | #ef4444 | 0° | — | 紧急 / 最高 |
| P1 | warning (橙) | #f59e0b | 30° | +30° | 高 / 重要 |
| P2 | **info (蓝)** | **#3b82f6** | **220°** | **+190°** | 普通 (默认) |
| P3 | fg-secondary (灰) | #a0a0a0 | n/a | — | 不急 |

**回归**: 162 → **164** tests pass (+2: badge 不变量测试 `test_priority_badge_styles_4_levels` 期望从 accent 改 info, 仍 pass; 整个 priority 套件跑过确认色值同步). `tsc --noEmit` 0 错误 (注意: .next/types/app/test-markdown 是 stale build artifact, 不是源代码错误).


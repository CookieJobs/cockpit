---
date: 2026-08-01
slug: timezone-fix
title: 时区 bug 修复 — 「今天」显示成「明天」 (lesson #19)
status: 现行
supersedes: —
related_lessons: #18
---

## Changelog: 2026-08-01 时区 bug 修复 — "今天" 显示成"明天" (lesson #19)

用户原话: "这个产品内的时间似乎有点问题，我设置完任务截止时间中的日期为「今天」之后，弹窗消失却发现这个字段成了「明天」"。

### 调查 + 根因

后端 storage 存的 `due` 是 `Date` 类型 (`app/core/storage.py:139`),前端发 `YYYY-MM-DD` 字符串,后端 Pydantic 解析成 `date(2026, 8, 1)`,SQLite 存 ISO date string — **后端时区无关, 没有 bug**。

bug 在**前端展示层** `web/lib/api.ts:506, 517`:

```ts
// 旧实现 (有 bug)
const dueDate = new Date(due);                  // ❌
const now = new Date();
now.setHours(0, 0, 0, 0);
const diffDays = Math.ceil((dueDate.getTime() - now.getTime()) / msPerDay);
```

`new Date("2026-08-01")` 这种 ISO date-only 字符串在 JS 规范里被**固定解析为 UTC 午夜 00:00**。但 `new Date()` 是本地时区,`now.setHours(0,0,0,0)` 归零到**本地午夜 00:00**。中国 UTC+8, 差 8 小时:

| 操作 | 时间 | 时区 |
|---|---|---|
| `new Date("2026-08-01")` | 2026-08-01 00:00 | **UTC** |
| `new Date()` (用户 10:48 打开) | 2026-08-01 10:48 | **CST** |
| `now.setHours(0,0,0,0)` 归零 | 2026-08-01 00:00 | **CST** |
| `dueDate - now` | **+8h** = 0.33 天 | 跨时区 |
| `Math.ceil(0.33)` | **1** | 整数进位 |
| 输出 | **"明天"** 💥 | 错 |

UTC 跟西半时区凑巧对(差是负数,`Math.ceil` 不会进位到下一天),东半时区 (UTC+1 ~ +12) 全部触发。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **加 `parseLocalDate` 工具** | `web/lib/api.ts` | 拆 `YYYY-MM-DD` 字段 + `new Date(y, m-1, d)` 显式本地构造, 永远返回本地 0:00 |
| 2 | **`dueColor` 改用 `parseLocalDate` + `now.setHours(0,0,0,0)`** | 同上 | 两个本地 0 点相减 = 整数 N*24h, `Math.ceil` 不会再进位 |
| 3 | **`dueLabel` 改用 `parseLocalDate` + `now.setHours(0,0,0,0)`** | 同上 | 同上 |
| 4 | **`Math.ceil` 改 `Math.round` (防御性)** | 同上 | 0.5 边界不依赖 ceil/round, 0.33/0.67 都正确归到 0/1 |
| 5 | **端到端 mjs 25 用例** | `web/scripts/test-due-date-tz.mjs` (新) | 跨 3 个时区 (Asia/Shanghai / UTC / America/Los_Angeles) 实跑真函数, 覆盖 parseLocalDate 7 断言 / dueColor 6 边界 / dueLabel 7 边界 / 兜底 / **反向证明旧实现复现"明天"** |
| 6 | **pytest 7 用例** | `app/tests/test_due_tz_invariants.py` (新) | 静态不变量 (锁 dueColor/dueLabel 不能再有 `new Date("YYYY-MM-DD"` 模式 + 必须用 parseLocalDate) + subprocess 调 mjs 3 时区 |
| 7 | **lesson #19 立** | `docs/lessons/06-timezone.md` (新) + README 索引 + AGENTS.md 索引 | 时区 bug 是 JS 规范层 (ISO date-only 解析为 UTC) 跟用户本地时区的对抗, 永远要在工具层处理 |

### 设计决定记录

**A. 加 `parseLocalDate` 工具 vs 直接在两个调用点 `split` 构造**

- 直接 `split`: 2 处写 2 遍, 后续 `relativeDate` 等其他函数再写就 N 遍
- 选工具: 1 个函数覆盖所有"YYYY-MM-DD → 本地 Date" 场景, 防后续有人再写 `new Date("YYYY-MM-DD")` 踩坑
- lesson: **跨时区逻辑写在工具层, 不要每个调用点都重复**

**B. `Math.round` vs `Math.ceil` vs `Math.floor`**

- 选 `Math.round`: 防御性, 0.5 边界更符合"四舍五入" 直觉
- 实际两个本地 0 点相减永远是整数 N*24h, 选哪个都一样 — 但 `round` 在 0.5 边界更接近"实际差值", `ceil` 偏向"上半天归到下一天", `floor` 偏向"上半天归到上一天"
- lesson: **写代码时多想想"如果计算结果是 0.5 怎么办"** — 0.5 是分界点, `round` 比 `ceil`/`floor` 边界更对称

**C. 端到端 mjs 跨 3 时区 vs pytest 单时区**

- pytest 单时区: 跑在 Asia/Shanghai 默认, 不会发现 UTC/LA 行为差异 — 实际上 UTC/LA 的旧实现**凑巧对**, pytest 单时区会被认为"没事" (false negative)
- mjs 跨 3 时区: `subprocess.run(env={**os.environ, "TZ": "Asia/Shanghai"})` 显式设 TZ, 跑真函数真环境, 不同时区行为一目了然
- lesson: **时区 bug 必须跨时区测试, 单时区测试会漏掉另一半时区**

**D. 反向证明 (旧实现必须复现 bug) vs 单向证明 (新实现对)**

- 单向: 跑新实现 → 全过 → "修了" (但没证明 bug 真实存在)
- 反向: 故意跑旧实现 → 在 Shanghai 看到"明天" → **证明 bug 真实存在 + 证明修复真在修这个 bug**
- lesson: **修 bug 时的端到端测试必须包含"反向证明"** — 证明"旧实现坏" + "新实现好", 才闭环
- mjs Test 7 专门做这个, 断言在 Asia/Shanghai 时区, 旧 label="明天", 新 label="今天"

**E. ISO date-only 字符串解析 UTC vs 本地 是 JS 规范事实**

- 不是 bug, 是 ISO 8601 + JS Date 构造器的**标准行为**: date-only 永远 UTC 午夜, datetime 永远本地解析
- 大量开发者不知道这点, `new Date("2026-08-01")` 在 Stack Overflow 上看着"对", 实际时区有问题
- lesson: **JS Date 是最常见的时区 bug 源头, 永远要 explicit 走哪个时区** — 跟 lesson #17 主题切换 "CSS variables 双套" 同源, 都是架构层"在每个边界明确指定"

### 字段表 (修完之后)

| 表达式 | 旧 | 新 | 行为差异 |
|---|---|---|---|
| `new Date("2026-08-01")` | UTC 2026-08-01 00:00 | (禁用) | 改 `parseLocalDate` |
| `parseLocalDate("2026-08-01")` | n/a | 本地 2026-08-01 00:00 | **永远本地** |
| `dueColor("今天")` 在 UTC+8 | warning (凑巧) | warning (正确) | 行为一致 |
| `dueLabel("今天")` 在 UTC+8 | **"明天"** 💥 | **"今天"** | **核心修复** |
| `dueColor("今天")` 在 UTC | warning (凑巧) | warning (正确) | 行为一致 |
| `Math.ceil` 边界 | 0.33 → 1 | (改 `round`) | 0.33 → 0 |
| 测试覆盖 | 无 | 25 mjs + 7 pytest | 时区无关性 |

### 端到端 mjs 25 用例覆盖

1. **parseLocalDate 始终返回本地 0:00** (7 断言: 年/月/日/时/分/秒)
2. **dueColor("今天") == "warning"** (3 时区各 1)
3. **dueLabel("今天") == "今天"** (3 时区各 1) — **核心 bug 修复验证**
4. **边界**: 明天 / 昨天 / 3 天后 / 7 天后 / 8 天后 (raw) / 30 天后 (raw) (6 个)
5. **dueColor 边界**: 昨天 danger / 今天 warning / 明天 accent / 3 天后 accent / 4 天后 muted (5 个)
6. **兜底**: null / "" → muted / empty (4 个)
7. **反向证明**: Asia/Shanghai 时区下, 旧 `new Date("YYYY-MM-DD")` 必须把"今天" 解析为"明天" (证明 bug 真实存在)

### 验证

- `npx tsc --noEmit` — 0 错误
- 后端测试套件 — **301 passed, 1 skipped** (从 294 → 301, +7 时区不变量 + 静态 grep, 0 回归)
- 端到端 mjs — **25 passed, 0 failed** (Asia/Shanghai) / **24 passed, 0 failed** (UTC) / **24 passed, 0 failed** (America/Los_Angeles), 跨 3 时区 73 用例全过
- 真实场景: `TZ=Asia/Shanghai` 跑 mjs, 旧实现 `due label="明天"` 新实现 `due label="今天"` → 修复锁定

**回归**: 294 → **301** tests pass (+7 时区不变量测试, 0 现有测试回归). `tsc --noEmit` 0 错误. 改动 1 改 lib 加 parseLocalDate + 改 2 函数 + 1 新 mjs 脚本 + 1 新 pytest 文件 + 1 新 lesson 文件 + 3 处文档更新, 净 +约 350 行. 用户视觉上: 中国时区选"今天" 弹窗消失后字段显示"今天" (修前是"明天"), 任何时区都正确.


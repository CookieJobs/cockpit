# 06 — 时区 Lessons

> Date 类型在前端解析时, 永远是"JS 规范" 跟"用户本地时区" 的对抗。
> 一旦代码用 `new Date("YYYY-MM-DD")` 直接解析字符串, 80% 概率潜伏时区 bug。

## #19. dueColor / dueLabel "今天" 显示成"明天" (修于 2026-08-01)

- **症状**: 用户报告"我设置完任务截止时间中的日期为「今天」之后, 弹窗消失却发现这个字段成了「明天」"。
- **根因**: `web/lib/api.ts:506, 517` 用 `new Date("2026-08-01")` 解析 `YYYY-MM-DD` 字符串。**JS 规范** 把这种 ISO date-only 字符串固定解析为 **UTC 午夜 00:00** (跟 ISO 8601 行为一致), 但 `new Date()` 当前时刻是**本地时区**。中国是 UTC+8, 差 8 小时。

  ```ts
  // 旧实现 (有 bug)
  const dueDate = new Date(due);                  // UTC 2026-08-01 00:00 = 本地 08:00
  const now = new Date();                         // 本地当前时刻 (例如 10:48)
  now.setHours(0, 0, 0, 0);                       // 归零到本地 00:00
  // diffMs = 08:00 - 00:00 = +8h
  // diffDays = 8h / 24h = 0.333
  // Math.ceil(0.333) = 1 → "明天"  💥
  ```

  中国早上 8:00 前选"今天" → 差 16h / 24h = 0.67 → ceil = 1 → "明天" (旧 bug)
  中国早上 8:00 后选"今天" → 差 8h / 24h = 0.33 → ceil = 1 → "明天" (旧 bug)

  任何**东半时区** (UTC+1 到 UTC+12) 都会触发, 因为 `Math.ceil` 把"不到一天"的小数差**永远进位到下一天**。UTC / 西半时区凑巧对 (差是负数, ceil 不会进位到下一天)。

- **修法**: 加 `parseLocalDate` 工具, **拆字段构造, 显式走本地时区**:

  ```ts
  export function parseLocalDate(s: string): Date {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);  // 走本地时区, 显式 0 点
  }
  ```

  `dueColor` / `dueLabel` 改用 `parseLocalDate(due)`, 跟 `now.setHours(0, 0, 0, 0)` 归零的本地 0 点对齐。两个本地 0 点相减永远是整数 N * 24h, 不会再触发 `Math.ceil` 进位到下一天。`Math.ceil` 也改 `Math.round` (防御性, 0.5 边界不依赖 ceil/round 选择)。

- **教训**:
  - **JS 中处理 `YYYY-MM-DD` 字符串永远不要 `new Date()`**: ISO date-only 解析为 UTC 午夜, 跟本地时间比较一定被时区偏移污染。
  - **跨时区思考要写在工具层**: 不要每个调用点都重复 `split + new Date(y, m-1, d)`, 抽 `parseLocalDate`, 防后续有人再写错。
  - **静态不变量 + 端到端 mjs 都要**: lesson #2/#15/#17 同源教训。单测/字符串 grep 只能锁"代码这么写", 不能锁"真实数据真这样"。mjs 跨 3 个时区 (UTC+8 / UTC / UTC-8) 实跑真函数, 锁住"今天" 永远显示"今天"。
  - **反向证明很重要**: lesson #19 的 mjs 脚本 Test 7 故意走旧的 `new Date("YYYY-MM-DD")` 解析方式, 断言"在 Asia/Shanghai 时区下, 旧实现对"今天" 解析为'明天'"。**证明 bug 真实存在** 而非想象, 防止后续有人"修法对吗" 的怀疑。
  - **永远本地时区 vs UTC 是产品决策**: 任务截止日期是"日历日" 概念, 用户选 "2026-08-01" 表达"在日历上 8 月 1 日那天" — **任何时区**都该是 8 月 1 日, 不是 UTC 8 月 1 日 0 点。所以必须本地解析, 永远本地。
- **修法位置**:
  - `web/lib/api.ts:504-527` 加 `parseLocalDate` + 改 `dueColor` / `dueLabel`
  - `web/scripts/test-due-date-tz.mjs` 端到端 25 用例, 3 个时区
  - `app/tests/test_due_tz_invariants.py` 静态 + subprocess 调 mjs, 7 用例

### 字段表 (修完之后)

| 旧实现 | 新实现 | 行为差异 |
|---|---|---|
| `new Date("2026-08-01")` → UTC 午夜 | `parseLocalDate("2026-08-01")` → 本地 0 点 | 时区无关性 |
| `Math.ceil(diff)` → "今天" 可能被进位到"明天" | `Math.round(diff)` → 整数 N, 0 不被进位 | 确定性 |
| 静态不变量缺失 | 静态 grep + mjs 端到端锁 | 防退化 |

### 端到端 mjs 用例覆盖 (25 个)

1. parseLocalDate 始终返回本地 0:00 (7 断言: 年/月/日/时/分/秒)
2. dueColor("今天") == "warning" (3 时区)
3. dueLabel("今天") == "今天" (3 时区) — **核心 bug 修复验证**
4. 边界: 明天 / 昨天 / 3 天后 / 7 天后 / 8 天后 (raw) / 30 天后 (raw)
5. dueColor 边界: 昨天 danger / 今天 warning / 明天 accent / 3 天后 accent / 4 天后 muted
6. 兜底: null / "" → muted / empty
7. **反向证明**: 旧实现必须在 Asia/Shanghai 时区把"今天" 解析为"明天" (复现用户报告)

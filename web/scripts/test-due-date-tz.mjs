// 2026-08-01 立: dueColor / dueLabel / parseLocalDate 端到端测试。
//
// 跑法: node --experimental-strip-types web/scripts/test-due-date-tz.mjs
//
// 真实 import lib/api.ts (无外部 React / Node 依赖), 验证:
//   1. parseLocalDate 在任何时区下都返回"本地 0 点"
//   2. dueColor("今天") 在 UTC+8 / UTC / UTC-8 都返回 "warning" (不是 "muted")
//   3. dueLabel("今天") 在上述 3 个时区都返回 "今天" (不是 "明天")
//   4. dueLabel("明天"/"昨天"/"3 天前"/"5 天后") 边界正确
//   5. due=null / undefined 兜底正确
//
// 锁 lesson #18 时区 bug: 旧实现 `new Date("2026-08-01")` 被 JS 规范化为 UTC 午夜,
// 跟本地 now 比差 8h (CST) → Math.ceil(0.33) = 1 → "今天" 显示成"明天"。
//
// 不锁退化 (静态不变量测试在 app/tests/test_due_tz_invariants.py),
// 这里只锁"真能跑 + 行为对", 跟 lesson #2/#15/#17 同源教训。

import { parseLocalDate, dueColor, dueLabel } from "../lib/api.ts";

// ---------------------------------------------------------------------------
// 工具: 取当前时区下的 "今天" 字符串 (YYYY-MM-DD)
// ---------------------------------------------------------------------------
function todayLocal() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

function shiftDays(base, delta) {
  // base 形如 "2026-08-01", delta=-1 → "2026-07-31" 等
  // 走本地时区, 避免跨月/跨年
  const [y, m, d] = base.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  const yy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

// ---------------------------------------------------------------------------
// 断言
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;
const failures = [];

function assertEq(actual, expected, name) {
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    failures.push(`✗ ${name}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// ---------------------------------------------------------------------------
// 测试 1: parseLocalDate 在任何时区都返回本地 0:00
// ---------------------------------------------------------------------------
console.log("=== Test 1: parseLocalDate 始终返回本地 0:00 ===");
{
  const t = todayLocal();
  const d = parseLocalDate(t);
  assertEq(d.getFullYear(), new Date().getFullYear(), "year == local year");
  assertEq(d.getMonth(), new Date().getMonth(), "month == local month");
  assertEq(d.getDate(), new Date().getDate(), "date == local date");
  assertEq(d.getHours(), 0, "hours == 0 (本地)");
  assertEq(d.getMinutes(), 0, "minutes == 0");
  assertEq(d.getSeconds(), 0, "seconds == 0");
}

// ---------------------------------------------------------------------------
// 测试 2: dueColor("今天") 任何时区都是 warning (lesson #18 核心)
// ---------------------------------------------------------------------------
console.log("=== Test 2: dueColor('今天') ===");
{
  const t = todayLocal();
  assertEq(dueColor(t), "warning", `[TZ=${process.env.TZ || "system"}] dueColor("今天") == "warning"`);
  // 反向证明: 跟旧 bug 对比, 旧实现 dueColor("今天") 在 UTC+8 可能返 "warning"
  // (凑巧覆盖) 但 dueLabel 会返 "明天" — 我们要锁住两函数都正确
}

// ---------------------------------------------------------------------------
// 测试 3: dueLabel("今天") 任何时区都返 "今天" (lesson #18 核心)
// ---------------------------------------------------------------------------
console.log("=== Test 3: dueLabel('今天') ===");
{
  const t = todayLocal();
  assertEq(dueLabel(t), "今天", `[TZ=${process.env.TZ || "system"}] dueLabel("今天") == "今天"`);
}

// ---------------------------------------------------------------------------
// 测试 4: 边界 (明天/昨天/N 天前/N 天后)
// ---------------------------------------------------------------------------
console.log("=== Test 4: 边界 ===");
{
  const t = todayLocal();
  assertEq(dueLabel(shiftDays(t, 1)), "明天", "明天");
  assertEq(dueLabel(shiftDays(t, -1)), "1天前", "昨天");
  assertEq(dueLabel(shiftDays(t, 3)), "3天后", "3 天后");
  assertEq(dueLabel(shiftDays(t, 7)), "7天后", "7 天后");
  assertEq(dueLabel(shiftDays(t, 8)), shiftDays(t, 8), "8 天后 -> raw string");
  assertEq(dueLabel(shiftDays(t, 30)), shiftDays(t, 30), "30 天后 -> raw string");
}

// ---------------------------------------------------------------------------
// 测试 5: dueColor 边界
// ---------------------------------------------------------------------------
console.log("=== Test 5: dueColor 边界 ===");
{
  const t = todayLocal();
  assertEq(dueColor(shiftDays(t, -1)), "danger", "昨天 -> danger (overdue)");
  assertEq(dueColor(t), "warning", "今天 -> warning");
  assertEq(dueColor(shiftDays(t, 1)), "accent", "明天 -> accent (1 天内)");
  assertEq(dueColor(shiftDays(t, 3)), "accent", "3 天后 -> accent (≤3)");
  assertEq(dueColor(shiftDays(t, 4)), "muted", "4 天后 -> muted");
  assertEq(dueColor(shiftDays(t, 30)), "muted", "30 天后 -> muted");
}

// ---------------------------------------------------------------------------
// 测试 6: 兜底 (null / 空串)
// ---------------------------------------------------------------------------
console.log("=== Test 6: 兜底 ===");
{
  assertEq(dueColor(null), "muted", "dueColor(null) -> muted");
  assertEq(dueLabel(null), "", "dueLabel(null) -> empty");
  assertEq(dueColor(""), "muted", "dueColor('') -> muted");
  assertEq(dueLabel(""), "", "dueLabel('') -> empty");
}

// ---------------------------------------------------------------------------
// 测试 7: 反向证明 — 旧实现 `new Date("YYYY-MM-DD")` 在 UTC+8 时区会失败
// (我们故意走旧的解析方式, 证明"如果不修, bug 真实存在")
// ---------------------------------------------------------------------------
console.log("=== Test 7: 反向证明旧实现的 bug ===");
{
  const t = todayLocal();
  // 旧实现: 直接 new Date("YYYY-MM-DD")
  const oldDue = new Date(t);
  const oldNow = new Date();
  oldNow.setHours(0, 0, 0, 0);
  const oldDiff = Math.ceil((oldDue.getTime() - oldNow.getTime()) / (1000 * 60 * 60 * 24));
  const oldLabel =
    oldDiff < 0 ? `${-oldDiff}天前`
    : oldDiff === 0 ? "今天"
    : oldDiff === 1 ? "明天"
    : oldDiff <= 7 ? `${oldDiff}天后`
    : t;

  // 在 UTC+8 时区, oldDue 是 UTC 午夜 = 本地 08:00, oldNow 是本地 00:00,
  // 差 +8h = 0.33 天, ceil = 1 → "明天" (跟用户报告一致)
  // 在 UTC 时区, oldDue == oldNow 都 0:00, 差 0 → "今天" (凑巧对)
  // 在 UTC-8 时区, oldDue 是 UTC 00:00 = 当地 16:00 昨天, oldNow 是当地 00:00 今天,
  // 差 = -16h = -0.67 天, ceil = 0 → "今天" (凑巧对)

  // 这个测试只做"日志记录", 不做断言 (因为时区不同时旧实现行为不同)。
  // 关键: 在 UTC+8 必须看到 "明天" (复现用户 bug)。
  console.log(`  [TZ=${process.env.TZ || "system"}] 旧实现对"今天" 解析:`);
  console.log(`    due=${t}, oldDue=${oldDue.toISOString()}, oldNow=${oldNow.toISOString()}`);
  console.log(`    diff=${oldDiff} 天, 旧 label="${oldLabel}", 新 label="${dueLabel(t)}"`);

  if ((process.env.TZ || "").includes("Shanghai")) {
    assertEq(oldLabel, "明天", "旧实现必须复现用户报告的 bug (今天 -> 明天)");
  }
}

// ---------------------------------------------------------------------------
// 汇总
// ---------------------------------------------------------------------------
console.log("\n=== 汇总 ===");
console.log(`✓ ${passed} passed`);
if (failed > 0) {
  console.log(`✗ ${failed} failed`);
  failures.forEach((f) => console.log(`  ${f}`));
  process.exit(1);
}
console.log(`(TZ=${process.env.TZ || "system"})`);

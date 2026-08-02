// 2026-08-02 立: cv-template.ts 端到端测试 (v0.4.2)
//
// 跑法: node --experimental-strip-types web/scripts/test-cv-template.mjs
//
// 真实 import lib/cv-template.ts, 验证:
//   - rangeToSince: "all" → null, "1y/2y/3y" → 当前日期 -N 年 (本地时区)
//   - filterByRange: 严格按 since 字符串比较 (date >= since)
//   - generateCvMarkdown: 空 → "", 多项目分组, 同项目按日期 desc
//
// 跟 test-theme-core.mjs 同模式 — 纯函数, 无 DOM 依赖, 直接测。

import {
  rangeToSince,
  filterByRange,
  generateCvMarkdown,
} from "../lib/cv-template.ts";

// ---------------------------------------------------------------------------
// 极简 assert
// ---------------------------------------------------------------------------
let passed = 0;
let failed = 0;
function assert(cond, msg) {
  if (cond) {
    passed++;
  } else {
    failed++;
    console.error(`❌ FAIL: ${msg}`);
  }
}
function group(name) {
  console.log(`\n=== ${name} ===`);
}

// ---------------------------------------------------------------------------
// Fake Achievement — 只用日期 + 项目 + cv 三字段, 其它填默认
// ---------------------------------------------------------------------------
const fake = (id, date, project, title, cv) => ({
  id,
  date,
  project_id: `pid_${project}`,
  project,
  title,
  outcome: "",
  reflection: "",
  cv,
  cv_status: "ready",
  tags: [],
  follow_up_questions: [],
  follow_up_answers: {},
});

// ---------------------------------------------------------------------------
// 1. rangeToSince
// ---------------------------------------------------------------------------
group("rangeToSince");

assert(rangeToSince("all") === null, '"all" must return null');

const since1y = rangeToSince("1y");
assert(typeof since1y === "string", '"1y" must return string');
assert(/^\d{4}-\d{2}-\d{2}$/.test(since1y), `"1y" must be YYYY-MM-DD, got ${since1y}`);

// 1 年前的年份 = 当前年 - 1
const now1 = new Date();
const expectedY1 = now1.getFullYear() - 1;
assert(
  since1y.startsWith(`${expectedY1}-`),
  `"1y" 应以 ${expectedY1}- 开头, got ${since1y}`,
);

const since3y = rangeToSince("3y");
const expectedY3 = now1.getFullYear() - 3;
assert(
  since3y.startsWith(`${expectedY3}-`),
  `"3y" 应以 ${expectedY3}- 开头, got ${since3y}`,
);

// ---------------------------------------------------------------------------
// 2. filterByRange
// ---------------------------------------------------------------------------
group("filterByRange");

const items = [
  fake("1", "2020-01-01", "远古项目", "远古任务", "远古 cv"),
  fake("2", "2024-06-15", "旧项目", "中期任务", "中期 cv"),
  fake("3", "2025-12-31", "近期项目", "近期任务", "近期 cv"),
];

// "all" → 全保留
const allResult = filterByRange(items, "all");
assert(allResult.length === 3, `"all" 应保留全部 3 条, got ${allResult.length}`);

// "1y" → 只保留 ≥ 1 年前
const oneYearResult = filterByRange(items, "1y");
const oneYearAgo = new Date();
oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
oneYearAgo.setHours(0, 0, 0, 0);
const oneYearAgoStr = `${oneYearAgo.getFullYear()}-${String(oneYearAgo.getMonth() + 1).padStart(2, "0")}-${String(oneYearAgo.getDate()).padStart(2, "0")}`;

const expectedAfter1y = items.filter((a) => a.date >= oneYearAgoStr).length;
assert(
  oneYearResult.length === expectedAfter1y,
  `"1y" 应保留 ${expectedAfter1y} 条, got ${oneYearResult.length}`,
);
// 验证 2020-01-01 必被排除 (除非 now 在 2021 年)
if (oneYearAgoStr > "2020-01-01") {
  assert(
    !oneYearResult.some((a) => a.id === "1"),
    `2020-01-01 应被 1y 范围排除 (since=${oneYearAgoStr})`,
  );
}

// "3y" → 应该包含 2020-01-01 之前的项目也可能 (取决于 now)
// 2020-01-01 跟 3 年前的关系: 取决于当前日期, 2026-08 → 3 年前 = 2023-08, 2020-01 必被排除
const threeYearAgo = new Date();
threeYearAgo.setFullYear(threeYearAgo.getFullYear() - 3);
threeYearAgo.setHours(0, 0, 0, 0);
const threeYearAgoStr = `${threeYearAgo.getFullYear()}-${String(threeYearAgo.getMonth() + 1).padStart(2, "0")}-${String(threeYearAgo.getDate()).padStart(2, "0")}`;
const threeYearResult = filterByRange(items, "3y");
if (threeYearAgoStr > "2020-01-01") {
  assert(
    !threeYearResult.some((a) => a.id === "1"),
    `2020-01-01 应被 3y 范围排除 (since=${threeYearAgoStr})`,
  );
}
assert(
  threeYearResult.some((a) => a.id === "3"),
  `2025-12-31 应保留 (任何合理 3y 范围都包含)`,
);

// ---------------------------------------------------------------------------
// 3. generateCvMarkdown
// ---------------------------------------------------------------------------
group("generateCvMarkdown");

// 空 → ""
assert(generateCvMarkdown([]) === "", "空列表应返回空字符串");

// 单条成就
const single = [fake("1", "2026-08-01", "A 项目", "完成 X", "主导 X 改版, DAU +5%")];
const singleMd = generateCvMarkdown(single);
assert(singleMd.includes("# 成就清单"), "单条应含 # 成就清单 标题");
assert(singleMd.includes("A 项目"), "单条应含项目名");
assert(singleMd.includes("2026-08-01"), "单条应含日期");
assert(singleMd.includes("完成 X"), "单条应含任务标题");
assert(singleMd.includes("主导 X 改版, DAU +5%"), "单条应含 CV 文本");
assert(singleMd.includes("1 条"), "单条应含计数 1 条");

// 多项目分组
const multi = [
  fake("1", "2026-07-01", "项目 A", "A 任务", "A cv"),
  fake("2", "2026-08-01", "项目 B", "B 任务", "B cv"),
  fake("3", "2026-06-01", "项目 A", "A 任务 2", "A2 cv"),
];
const multiMd = generateCvMarkdown(multi);
assert(multiMd.includes("## 项目 A"), "应含 ## 项目 A 标题");
assert(multiMd.includes("## 项目 B"), "应含 ## 项目 B 标题");
// 同一项目多条按日期 desc
const idxA1 = multiMd.indexOf("A 任务"); // 2026-07-01
const idxA2 = multiMd.indexOf("A 任务 2"); // 2026-06-01
assert(idxA1 < idxA2, `项目 A 内 desc 排序错: 2026-07-01(${idxA1}) 应在 2026-06-01(${idxA2}) 之前`);

// 项目顺序: 按项目内最早日期 desc (最近做的项目最显眼)
const idxProjA = multiMd.indexOf("## 项目 A");
const idxProjB = multiMd.indexOf("## 项目 B");
// 项目 A 最早 = 2026-06-01, 项目 B 最早 = 2026-08-01 → B 排在前
assert(idxProjB < idxProjA, `项目顺序错: 项目 B(2026-08 最早)${idxProjB} 应在项目 A(2026-06 最早)${idxProjA} 之前`);

// 计数
assert(multiMd.includes("3 条"), "应含计数 3 条");

// ---------------------------------------------------------------------------
// 4. 空项目名兜底
// ---------------------------------------------------------------------------
group("edge case: 空项目名");

const orphan = [fake("o1", "2026-08-01", "", "孤儿任务", "孤儿 cv")];
const orphanMd = generateCvMarkdown(orphan);
assert(orphanMd.includes("(未命名项目)"), "空项目名应兜底为 (未命名项目)");

// ---------------------------------------------------------------------------
// 结果
// ---------------------------------------------------------------------------
console.log(`\n=== 结果 ===`);
console.log(`✅ ${passed} passed, ❌ ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);

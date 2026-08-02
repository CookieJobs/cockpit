// 2026-08-02 立: achievement-stats.ts 端到端测试 (v0.3.5)
//
// 跑法: node --experimental-strip-types web/scripts/test-achievement-stats.mjs
//
// 真实 import lib/achievement-stats.ts, 验证:
//   - computeStats: 空 / 全 ready / 混合状态 / 量化识别 / 强动词识别
//   - ratioToPct: 四舍五入
//   - gradeRatio: 4 档评级

import {
  computeStats,
  ratioToPct,
  gradeRatio,
  verbDistribution,
  STRONG_VERBS,
  WEAK_VERBS,
} from "../lib/achievement-stats.ts";

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
// Fake Achievement
// ---------------------------------------------------------------------------
const fake = (id, cv_status, cv) => ({
  id,
  date: "2026-08-01",
  project_id: "p1",
  project: "P",
  title: `t${id}`,
  outcome: "",
  reflection: "",
  cv,
  cv_status,
  tags: [],
  follow_up_questions: [],
  follow_up_answers: {},
});

// ---------------------------------------------------------------------------
// 1. 常量完整性
// ---------------------------------------------------------------------------
group("常量完整性");

assert(STRONG_VERBS.length >= 10, `STRONG_VERBS 应至少 10 个, 实际 ${STRONG_VERBS.length}`);
assert(STRONG_VERBS.includes("构建") && STRONG_VERBS.includes("主导"),
  "STRONG_VERBS 必含核心强动词");
assert(WEAK_VERBS.length >= 4, `WEAK_VERBS 应至少 4 个, 实际 ${WEAK_VERBS.length}`);
assert(WEAK_VERBS.includes("负责") && WEAK_VERBS.includes("参与"),
  "WEAK_VERBS 必含核心弱动词");
// 强/弱不能有交集
const overlap = STRONG_VERBS.filter((v) => WEAK_VERBS.includes(v));
assert(overlap.length === 0, `强/弱动词不能有交集, 实际交集: ${overlap}`);

// ---------------------------------------------------------------------------
// 2. computeStats 边界
// ---------------------------------------------------------------------------
group("computeStats 边界");

// 空数组
const empty = computeStats([]);
assert(empty.total === 0, "空数组 total=0");
assert(empty.ready_ratio === 0, "空数组 ready_ratio=0");
assert(empty.quantify_ratio === 0, "空数组 quantify_ratio=0");

// 单条 ready
const oneReady = computeStats([fake("1", "ready", "主导 App 改版, DAU 提升 5%")]);
assert(oneReady.total === 1, "单条 total=1");
assert(oneReady.ready === 1, "单条 ready=1");
assert(oneReady.ready_ratio === 1, "单条 ready_ratio=1");
assert(oneReady.quantify_count === 1, "单条 quantify_count=1 (DAU 5%)");
assert(oneReady.strong_verb_count === 1, "单条 strong_verb=1 (主导 开头)");

// 单条 weak cv (没量化, 弱动词)
const oneWeak = computeStats([fake("1", "pending", "完成了任务")]);
assert(oneWeak.quantify_count === 0, "弱 cv quantify=0");
assert(oneWeak.strong_verb_count === 0, "弱 cv strong_verb=0 (完成 不是强动词)");
// 注意: ready_ratio 是 0/1 = 0 (pending 不算 ready)

// ---------------------------------------------------------------------------
// 3. computeStats 量化识别 (各种量化形式)
// ---------------------------------------------------------------------------
group("量化识别");

const quantifyCases = [
  ["DAU 提升 5%", true],          // 5% 匹配
  ["10 万用户", true],            // 10 万 匹配
  ["3 个模块", true],             // 3 个 匹配
  ["节省 2 小时/天", true],       // 2 时 匹配
  ["800ms 降至 200ms", true],     // 800ms 匹配
  ["QPS 提升 50%", true],         // QPS 匹配
  ["接口响应时间从 800ms 降至 200ms", true],  // 800ms 200ms 都匹配
  ["覆盖 5 万用户", true],        // 5 万
  ["影响了登录流程", false],       // 无量化
  ["修复了用户模块", false],       // 无量化
];

for (const [cv, expected] of quantifyCases) {
  const result = computeStats([fake("1", "ready", cv)]);
  assert(
    result.quantify_count === (expected ? 1 : 0),
    `量化识别 [${cv}]: expected ${expected ? 1 : 0}, got ${result.quantify_count}`,
  );
}

// ---------------------------------------------------------------------------
// 4. computeStats 强动词识别
// ---------------------------------------------------------------------------
group("强动词识别");

const verbCases = [
  ["主导 App 改版", "主导", true],
  ["设计 XX 模块", "设计", true],
  ["重构用户模块拆分 3 个微服务", "重构", true],
  ["推动 X 项目落地", "推动", true],
  ["优化接口响应", "优化", true],
  ["修复登录 bug", "修复", true],
  ["构建 XX 平台", "构建", true],
  ["完成了任务", "完成", false],  // 完成 不在强动词清单
  ["负责 XX 模块", "负责", false],  // 弱动词
  ["参与了 XX 项目", "参与", false],  // 弱动词
  ["做了 PRD 撰写", "做了", false],  // 弱动词
];

for (const [cv, _, expected] of verbCases) {
  const result = computeStats([fake("1", "ready", cv)]);
  assert(
    result.strong_verb_count === (expected ? 1 : 0),
    `强动词 [${cv}]: expected ${expected ? 1 : 0}, got ${result.strong_verb_count}`,
  );
}

// ---------------------------------------------------------------------------
// 5. computeStats 混合状态
// ---------------------------------------------------------------------------
group("混合状态");

const mixed = [
  fake("1", "ready", "主导 X, DAU +5%"),          // 量化 + 强动词
  fake("2", "ready", "设计 Y 模块"),              // 无量化 + 强动词
  fake("3", "needs_data", "完成了 Z (具体指标待补)"),  // 无量化 + 弱
  fake("4", "pending", "做了一下"),                 // 无量化 + 弱
  fake("5", "ready", "参与了 X"),                  // 无量化 + 弱
];
const m = computeStats(mixed);
assert(m.total === 5, "total=5");
assert(m.ready === 3, "ready=3");
assert(m.needs_data === 1, "needs_data=1");
assert(m.pending === 1, "pending=1");
assert(m.ready_ratio === 0.6, `ready_ratio=0.6, got ${m.ready_ratio}`);
// 量化: 只有 #1 含量化 (DAU +5%) — 修正之前的错误期望
assert(m.quantify_count === 1, `quantify=1 (#1 DAU+5%), got ${m.quantify_count}`);
// 强动词: 1,2 = 2 条 (#3 完成 不算强动词)
assert(m.strong_verb_count === 2, `strong_verb=2 (1,2), got ${m.strong_verb_count}`);

// ---------------------------------------------------------------------------
// 6. ratioToPct
// ---------------------------------------------------------------------------
group("ratioToPct");

assert(ratioToPct(0) === 0, "0 → 0%");
assert(ratioToPct(0.5) === 50, "0.5 → 50%");
assert(ratioToPct(0.654) === 65, "0.654 → 65% (四舍五入)");
assert(ratioToPct(0.666) === 67, "0.666 → 67% (四舍五入)");
assert(ratioToPct(1) === 100, "1 → 100%");

// ---------------------------------------------------------------------------
// 7. gradeRatio
// ---------------------------------------------------------------------------
group("gradeRatio");

const grade0 = gradeRatio(0);
assert(grade0.label === "待提升" && grade0.color === "text-danger", `0 → 待提升/danger, got ${grade0.label}/${grade0.color}`);
const grade50 = gradeRatio(0.5);
assert(grade50.label === "一般" && grade50.color === "text-warning", `50% → 一般/warning, got ${grade50.label}/${grade50.color}`);
const grade70 = gradeRatio(0.7);
assert(grade70.label === "良好" && grade70.color === "text-accent", `70% → 良好/accent, got ${grade70.label}/${grade70.color}`);
const grade90 = gradeRatio(0.9);
assert(grade90.label === "优秀" && grade90.color === "text-success", `90% → 优秀/success, got ${grade90.label}/${grade90.color}`);

// ---------------------------------------------------------------------------
// 8. verbDistribution (v0.4.3 立)
// ---------------------------------------------------------------------------
group("verbDistribution");

// 空数组
const emptyDist = verbDistribution([]);
assert(emptyDist.length === 0, "空数组应返空");

// 多种强动词
const dist1 = verbDistribution([
  fake("1", "ready", "主导 X 项目, DAU +5%"),
  fake("2", "ready", "主导 Y 模块"),
  fake("3", "ready", "设计 Z 平台"),
  fake("4", "ready", "重构 A 模块"),
  fake("5", "ready", "设计 B 页面"),
]);
assert(dist1.length === 3, `应有 3 种强动词, got ${dist1.length}`);
// 顺序: count desc → verb asc
// 主导(2) / 设计(2) / 重构(1)
assert(dist1[0].verb === "主导" && dist1[0].count === 2, `第 1 应是 主导=2, got ${JSON.stringify(dist1[0])}`);
assert(dist1[1].verb === "设计" && dist1[1].count === 2, `第 2 应是 设计=2, got ${JSON.stringify(dist1[1])}`);
assert(dist1[2].verb === "重构" && dist1[2].count === 1, `第 3 应是 重构=1, got ${JSON.stringify(dist1[2])}`);

// 含弱动词开头 → 归 "(其他)"
const dist2 = verbDistribution([
  fake("1", "ready", "主导 X"),
  fake("2", "pending", "负责 Y"),  // 弱
  fake("3", "ready", "参与了 Z"),  // 弱
  fake("4", "ready", "做了 Q"),  // 弱
]);
assert(dist2.length === 2, `应有 2 项 (主导 + 其他), got ${dist2.length}`);
assert(dist2[0].verb === "主导" && dist2[0].count === 1, `第 1 主导=1`);
assert(dist2[1].verb === "(其他)" && dist2[1].count === 3, `第 2 (其他)=3, got ${JSON.stringify(dist2[1])}`);

// 同 count 按 verb asc (稳定排序)
const dist3 = verbDistribution([
  fake("1", "ready", "设计 X"),
  fake("2", "ready", "主导 Y"),
  fake("3", "ready", "重构 Z"),
  fake("4", "ready", "优化 Q"),
]);
// 全是 1, 按 verb asc: 主导(1) / 优化(1) / 设计(1) / 重构(1)
const verbs = dist3.map((d) => d.verb);
assert(
  JSON.stringify(verbs) === JSON.stringify(["主导", "优化", "设计", "重构"]),
  `同 count 应按 verb asc 排序, got ${verbs}`,
);

// 全部是弱动词 → 只有 "(其他)"
const dist4 = verbDistribution([
  fake("1", "ready", "负责 X"),
  fake("2", "ready", "参与了 Y"),
]);
assert(dist4.length === 1, `全弱动词应只有 1 项`);
assert(dist4[0].verb === "(其他)" && dist4[0].count === 2, "(其他)=2");

// 空 cv 文本应被忽略
const dist5 = verbDistribution([
  fake("1", "ready", ""),
  fake("2", "ready", "主导 X"),
]);
assert(dist5.length === 1 && dist5[0].count === 1, "空 cv 应忽略");

// ---------------------------------------------------------------------------
// 结果
// ---------------------------------------------------------------------------
console.log(`\n=== 结果 ===`);
console.log(`✅ ${passed} passed, ❌ ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);

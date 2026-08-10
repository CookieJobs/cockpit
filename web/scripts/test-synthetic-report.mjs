import assert from "node:assert/strict";
import { generateSyntheticReport } from "./generate-synthetic-report.mjs";

const achievements = [
  {
    id: "ready_1", date: "2026-07-06", task_id: "task_1", project_id: "project_1",
    project: "新手引导优化", title: "梳理激活漏斗", outcome: "完成访谈", reflection: "",
    cv: "完成 5 位新用户访谈，定位首屏流失环节。", cv_status: "ready", tags: [],
    follow_up_questions: [], follow_up_answers: {},
  },
  {
    id: "needs_data_1", date: "2026-07-06", task_id: "task_2", project_id: "project_1",
    project: "新手引导优化", title: "补充留存对比", outcome: "等待样本", reflection: "",
    cv: "待补充留存证据。", cv_status: "needs_data", tags: [],
    follow_up_questions: ["留存结论是什么？"], follow_up_answers: {},
  },
];

const report = generateSyntheticReport(achievements, {
  since: "2026-07-01",
  until: "2026-07-07",
  label: "第 1 周",
});

assert.deepEqual(report.usedAchievementIds, ["ready_1"]);
assert.match(report.markdown, /完成 5 位新用户访谈/);
assert.doesNotMatch(report.markdown, /待补充留存证据/);
assert.equal(report.window.since, "2026-07-01");
console.log("synthetic report adapter: passed");

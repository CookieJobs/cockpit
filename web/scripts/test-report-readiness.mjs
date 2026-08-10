import assert from "node:assert/strict";
import { TEMPLATES, generateReport } from "../lib/templates.ts";

const range = { key: "test", label: "测试", description: "", since: () => "2026-08-01", until: () => "2026-08-10" };
const achievement = (status, cv) => ({ id: status, project: "Cockpit", title: cv, outcome: cv, reflection: "", cv, cv_status: status, date: "2026-08-10", task_id: status, project_id: "p", tags: [], follow_up_questions: [], follow_up_answers: {} });

const report = generateReport([
  achievement("ready", "上线核心功能并完成验收"),
  achievement("needs_data", "优化内容，缺少指标"),
  achievement("pending", "草稿"),
], range, TEMPLATES[0]);

assert.equal(report.usedAchievements.length, 1);
assert(report.markdown.includes("上线核心功能并完成验收"));
assert(!report.markdown.includes("优化内容，缺少指标"));
assert(!report.markdown.includes("草稿"));
console.log("✅ report readiness passed");

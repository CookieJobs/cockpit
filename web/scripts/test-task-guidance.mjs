#!/usr/bin/env node
/**
 * 端到端测试: 跑 taskGuidance.ts 的 classifyTaskTitle 函数对真实任务标题分类.
 * 2026-07-30 立, lesson #15 盲点修复.
 *
 * 用法: cd web && node --experimental-strip-types scripts/test-task-guidance.mjs
 * 退出码: 0 = 全部通过, 1 = 有失败
 */
import { classifyTaskTitle } from "../lib/taskGuidance.ts";

const cases = [
  // [任务标题, 期望分类, 备注]
  ["修登录鉴权 bug", "fix", "用户实测误判 case (lesson #15 盲点)"],
  ["修bug", "fix"],
  ["修复登录", "fix"],
  ["修线上问题", "fix"],
  ["解决内存泄漏", "fix"],
  ["排查线上 crash", "fix"],
  ["重构 ChatWindow 墨式状态机", "fix"],
  ["debug 一下", "fix"],
  ["系统崩溃了", "fix"],
  ["闪退问题", "fix"],
  ["完成 PRD", "artifact"],
  ["写完 Q3 述职草稿", "artifact"],
  ["周末写小红书选题", "artifact"],
  ["做技术分享 PPT", "artifact"],
  ["写周报", "artifact"],
  ["整理述职材料", "artifact"],
  ["开 Q3 复盘会", "discussion"],
  ["跟设计同步改版", "discussion"],
  ["1on1", "discussion"],
  ["调研 3 家 SSO 厂商", "research"],
  ["对比 A vs B 方案", "research"],
];

let pass = 0;
let fail = 0;
const fails = [];

for (const [title, expected, note] of cases) {
  const got = classifyTaskTitle(title);
  if (got === expected) {
    pass++;
    console.log(`  ✓ "${title}" → ${got}`);
  } else {
    fail++;
    fails.push({ title, expected, got, note: note || "" });
    console.log(`  ✗ "${title}" → ${got} (期望 ${expected}) ${note ? `[${note}]` : ""}`);
  }
}

console.log(`\n=== ${pass} 通过, ${fail} 失败 / ${cases.length} 总数 ===`);

if (fail > 0) {
  console.log("\n失败明细:");
  for (const f of fails) {
    console.log(`  - "${f.title}": 期望 ${f.expected}, 实际 ${f.got} ${f.note ? `[${f.note}]` : ""}`);
  }
  process.exit(1);
}

console.log("\n所有 case 通过 ✓");
process.exit(0);

// CV 模板生成 (2026-08-02 v0.4.2 立)
//
// 跟 lib/templates.ts 的"周报/述职"模板同思路, 但:
// - 纯结构化拼装, 不调 LLM
// - 输入是 ready 成就列表 (全量, 不过滤时间 — 时间过滤在 /cv 页 UI 做)
// - 输出是可直接贴简历的 markdown
//
// v0.7 统一输出引擎会在此基础上加 LLM 润色 + 多模板切换

import type { Achievement } from "./api";

export type CvRangePreset = "1y" | "2y" | "3y" | "all";

// 时间范围 → 起始日期 (YYYY-MM-DD), 全部 = null
export function rangeToSince(preset: CvRangePreset): string | null {
  if (preset === "all") return null;
  const d = new Date();
  d.setFullYear(d.getFullYear() - Number(preset.replace("y", "")));
  // 本地时区归零 (lesson #19 — parseLocalDate 思路)
  d.setHours(0, 0, 0, 0);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// 按范围预设过滤成就
export function filterByRange(
  items: Achievement[],
  preset: CvRangePreset,
): Achievement[] {
  const since = rangeToSince(preset);
  if (!since) return items;
  return items.filter((a) => a.date >= since);
}

// 按日期倒序排 (新 → 旧, 简历读者视角)
function sortByDateDesc(items: Achievement[]): Achievement[] {
  return [...items].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
}

// 按 project 分组 (不按时间分, 跨项目聚合)
function groupByProject(items: Achievement[]): Map<string, Achievement[]> {
  const map = new Map<string, Achievement[]>();
  for (const a of items) {
    const key = a.project || "(未命名项目)";
    const arr = map.get(key) || [];
    arr.push(a);
    map.set(key, arr);
  }
  // 项目内按日期 desc
  for (const [k, arr] of map.entries()) {
    map.set(k, sortByDateDesc(arr));
  }
  return map;
}

// 生成 markdown
export function generateCvMarkdown(items: Achievement[]): string {
  if (items.length === 0) return "";
  const sorted = sortByDateDesc(items);
  const grouped = groupByProject(sorted);

  // 标题 + 简介
  const lines: string[] = [];
  lines.push(`# 成就清单`);
  lines.push(``);
  lines.push(
    `> 生成时间: ${new Date().toISOString().slice(0, 10)} · 累计 ${items.length} 条 ready 成就`,
  );
  lines.push(``);

  // 项目分组 (按项目内最早日期 desc 排, 最近做的项目最显眼)
  const projectOrder = Array.from(grouped.entries())
    .map(([name, items]) => {
      const earliest = items[items.length - 1].date;
      return { name, items, earliest };
    })
    .sort((a, b) => (a.earliest < b.earliest ? 1 : -1));

  for (const { name, items } of projectOrder) {
    lines.push(`## ${name}`);
    lines.push(``);
    for (const a of items) {
      // 每条成就: 日期 + 任务标题 + CV
      lines.push(`- **${a.date}** · ${a.title}`);
      lines.push(`  ${a.cv}`);
    }
    lines.push(``);
  }

  return lines.join("\n");
}

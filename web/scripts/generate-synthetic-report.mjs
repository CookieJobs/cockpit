/** Generate a ready-only synthetic artefact without depending on product UI templates. */

import { readFile } from "node:fs/promises";

function isInWindow(achievement, since, until) {
  return achievement.date >= since && achievement.date <= until;
}

export function generateSyntheticReport(achievements, window) {
  const readyInWindow = achievements.filter(
    (achievement) =>
      achievement.cv_status === "ready" &&
      isInWindow(achievement, window.since, window.until),
  );
  const projects = new Map();
  for (const achievement of readyInWindow) {
    const name = achievement.project || "未分类";
    projects.set(name, [...(projects.get(name) || []), achievement]);
  }
  const lines = [`## ${window.label}周报（${window.since} ~ ${window.until}）`, "", "### 已完成"];
  if (projects.size === 0) lines.push("- 本时间范围内没有可直接使用的成果。");
  for (const name of [...projects.keys()].sort((left, right) => left.localeCompare(right, "zh-CN"))) {
    lines.push(`### ${name}`);
    for (const achievement of projects.get(name)) lines.push(`- ${achievement.cv || achievement.outcome || achievement.title}`);
    lines.push("");
  }
  return {
    synthetic: true,
    window,
    markdown: `${lines.join("\n").trim()}\n`,
    usedAchievementIds: readyInWindow.map((achievement) => achievement.id),
  };
}

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  return index === -1 ? undefined : process.argv[index + 1];
}

async function main() {
  const input = argumentValue("--input");
  const since = argumentValue("--since");
  const until = argumentValue("--until");
  const label = argumentValue("--label") ?? "模拟覆盖";
  if (!input || !since || !until) {
    throw new Error("usage: --input <snapshot.json> --since YYYY-MM-DD --until YYYY-MM-DD [--label text]");
  }
  const parsed = JSON.parse(await readFile(input, "utf8"));
  const achievements = Array.isArray(parsed) ? parsed : parsed.achievements;
  if (!Array.isArray(achievements)) throw new Error("input must be an achievement array or { achievements: [...] }");
  process.stdout.write(`${JSON.stringify(generateSyntheticReport(achievements, { since, until, label }), null, 2)}\n`);
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}

/** Generate a ready-only report artefact through Cockpit's existing template layer. */

import { readFile } from "node:fs/promises";
import { TEMPLATES, generateReport } from "../lib/templates.ts";

function isInWindow(achievement, since, until) {
  return achievement.date >= since && achievement.date <= until;
}

export function generateSyntheticReport(achievements, window) {
  const template = TEMPLATES.find((item) => item.key === "product_weekly");
  if (!template) throw new Error("product_weekly template is unavailable");

  const readyInWindow = achievements.filter(
    (achievement) =>
      achievement.cv_status === "ready" &&
      isInWindow(achievement, window.since, window.until),
  );
  const range = {
    key: `synthetic_${window.since}_${window.until}`,
    label: window.label,
    description: "Synthetic dogfooding coverage window",
    since: () => window.since,
    until: () => window.until,
  };
  const generated = generateReport(readyInWindow, range, template);
  return {
    synthetic: true,
    window,
    markdown: generated.markdown,
    usedAchievementIds: generated.usedAchievements.map((achievement) => achievement.id),
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

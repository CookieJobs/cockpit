import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("..", import.meta.url);
const cv = readFileSync(new URL("app/cv/page.tsx", root), "utf8");
const report = readFileSync(new URL("app/report/page.tsx", root), "utf8");
const templates = readFileSync(new URL("lib/templates.ts", root), "utf8");

assert.match(cv, /redirect\("\/report\?type=cv&range=all"\)/);
assert.doesNotMatch(cv, /listAchievements|generateCvMarkdown/);
assert.match(report, /useSearchParams/);
assert.match(report, /searchParams\.get\("type"\)/);
assert.match(report, /searchParams\.get\("range"\)/);
assert.match(templates, /key:\s*"cv"/);
assert.match(templates, /key:\s*"all"/);

console.log("output center: pass");

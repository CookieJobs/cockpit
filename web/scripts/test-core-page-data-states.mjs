import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("..", import.meta.url);
const files = [
  "components/MainBoard.tsx",
  "app/achievements/page.tsx",
  "app/report/page.tsx",
  "app/settings/page.tsx",
];

for (const relativePath of files) {
  const source = readFileSync(new URL(relativePath, root), "utf8");
  assert.match(source, /isLoading/);
  assert.match(source, /DataState/);
  assert.match(source, /onRetry/);
}

console.log("core page data states: pass");

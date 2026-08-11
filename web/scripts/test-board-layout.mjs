import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let passed = 0;

function test(name, run) {
  try {
    run();
    passed += 1;
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}`);
    throw error;
  }
}

console.log("# MainBoard responsive layout");

test("MainBoard compilation emits both mobile overlay and desktop rail rules", () => {
  const outputDir = mkdtempSync(join(tmpdir(), "cockpit-mainboard-tailwind-"));
  const outputPath = join(outputDir, "mainboard.css");
  try {
    execFileSync(
      "./node_modules/.bin/tailwindcss",
      [
        "-c",
        "tailwind.config.ts",
        "-i",
        "app/globals.css",
        "-o",
        outputPath,
        "--content",
        "./components/MainBoard.tsx",
      ],
      { stdio: "pipe" },
    );
    const compiled = readFileSync(outputPath, "utf8");
    assert.match(compiled, /\.fixed\s*\{\s*position: fixed;/s);
    assert.match(compiled, /\.md\\:static\s*\{\s*position: static;/s);
    assert.match(compiled, /\.md\\:flex-col\s*\{\s*flex-direction: column;/s);
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});

console.log(`\n=== ${passed} passed, 0 failed ===`);

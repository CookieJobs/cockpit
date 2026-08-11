import assert from "node:assert/strict";
import { getChatPanelClassName, getChatLauncherClassName } from "../lib/board-layout.ts";

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

test("open chat covers the viewport on narrow screens but remains a desktop side panel", () => {
  const className = getChatPanelClassName();
  assert.match(className, /fixed inset-0 z-30/);
  assert.match(className, /md:static/);
  assert.match(className, /md:w-\[35%\]/);
});

test("closed chat is a floating mobile launcher and a fixed-width desktop rail", () => {
  const className = getChatLauncherClassName();
  assert.match(className, /fixed bottom-4 right-4 z-20/);
  assert.match(className, /md:static/);
  assert.match(className, /md:w-11/);
});

console.log(`\n=== ${passed} passed, 0 failed ===`);

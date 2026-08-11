// 2026-08-11 立：视觉语义层的行为契约。
//
// 跑法：node --experimental-strip-types scripts/test-visual-tokens.mjs
//
// 真正 import 供组件使用的映射，而非扫描 CSS 源码。这样如果某一角色
// 被错误复用成另一个角色的视觉处理，测试会直接失败。

import { getVisualTone } from "../lib/visual-system.ts";

let pass = 0;
let fail = 0;

function check(name, condition, detail = "") {
  if (condition) {
    pass += 1;
    console.log(`  ✓ ${name}`);
  } else {
    fail += 1;
    console.log(`  ✗ ${name}${detail ? ` — ${detail}` : ""}`);
  }
}

function section(name) {
  console.log(`\n# ${name}`);
}

section("semantic role treatments");
const interaction = getVisualTone("interaction", "soft");
const asset = getVisualTone("asset", "soft");
const warning = getVisualTone("warning", "soft");

check("interaction 使用 accent", interaction.includes("accent"), interaction);
check("asset 使用 asset 而非 accent", asset.includes("asset") && !asset.includes("accent"), asset);
check("warning 使用 warning 而非 accent", warning.includes("warning") && !warning.includes("accent"), warning);
check("三个角色的 soft treatment 彼此不同", new Set([interaction, asset, warning]).size === 3,
  `${interaction} / ${asset} / ${warning}`);

section("solid roles remain readable in both themes");
for (const role of ["interaction", "asset", "warning"]) {
  const solid = getVisualTone(role, "solid");
  check(`${role} solid 使用自己的背景色`, solid.includes(`bg-${role === "interaction" ? "accent" : role}`), solid);
  check(`${role} solid 使用 tokenized foreground`, solid.includes("text-bg"), solid);
}

if (fail > 0) {
  console.error(`\n${fail} failed, ${pass} passed`);
  process.exit(1);
}

console.log(`\n${pass} passed`);

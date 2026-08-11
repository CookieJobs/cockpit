// 2026-08-11 立：视觉语义层的行为契约。
//
// 跑法：node --experimental-strip-types scripts/test-visual-tokens.mjs
//
// 真正 import 供组件使用的映射，而非扫描 CSS 源码。这样如果某一角色
// 被错误复用成另一个角色的视觉处理，测试会直接失败。

import { getVisualTone } from "../lib/visual-system.ts";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

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

function readRgbToken(scope, token) {
  const source = readFileSync("app/globals.css", "utf8");
  const block = source.match(new RegExp(`${scope.replace(".", "\\.")}\\s*\\{([\\s\\S]*?)\\n\\}`));
  const match = block?.[1].match(new RegExp(`--color-${token}:\\s*(\\d+)\\s+(\\d+)\\s+(\\d+)`));
  return match ? match.slice(1).map(Number) : null;
}

function relativeLuminance([red, green, blue]) {
  const linear = [red, green, blue].map((value) => {
    const channel = value / 255;
    return channel <= 0.04045
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastAgainstWhite(rgb) {
  return 1.05 / (relativeLuminance(rgb) + 0.05);
}

function hue([red, green, blue]) {
  const [r, g, b] = [red, green, blue].map((value) => value / 255);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;
  if (delta === 0) return 0;
  const base = max === r ? ((g - b) / delta) % 6 : max === g ? (b - r) / delta + 2 : (r - g) / delta + 4;
  return (base * 60 + 360) % 360;
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

section("theme token distinction");
const lightAsset = readRgbToken(":root", "asset");
const lightWarning = readRgbToken(":root", "warning");
const darkBg = readRgbToken(".dark", "bg");
const darkSecondary = readRgbToken(".dark", "bg-secondary");
check("light asset token exists", Array.isArray(lightAsset), String(lightAsset));
check("light warning token exists", Array.isArray(lightWarning), String(lightWarning));
if (lightAsset && lightWarning) {
  const hueDistance = Math.abs(hue(lightAsset) - hue(lightWarning));
  check("light asset 与 warning 至少相差 20° 色相", Math.min(hueDistance, 360 - hueDistance) >= 20,
    `${hue(lightAsset).toFixed(1)}° / ${hue(lightWarning).toFixed(1)}°`);
  check("light asset 在白底的文字对比度达到 AA", contrastAgainstWhite(lightAsset) >= 4.5,
    contrastAgainstWhite(lightAsset).toFixed(2));
}
check("dark bg token exists", Array.isArray(darkBg), String(darkBg));
check("dark secondary token exists", Array.isArray(darkSecondary), String(darkSecondary));
if (darkBg && darkSecondary) {
  const channelDelta = Math.max(...darkSecondary.map((value, index) => Math.abs(value - darkBg[index])));
  check("dark secondary 比 bg 至少亮 8 个通道值", channelDelta >= 8, String(channelDelta));
}

section("Tailwind runtime compilation");
const tempDir = mkdtempSync(join(tmpdir(), "cockpit-visual-tokens-"));
const output = join(tempDir, "tokens.css");
try {
  execFileSync("./node_modules/.bin/tailwindcss", ["-c", "tailwind.config.ts", "-i", "app/globals.css", "-o", output], {
    stdio: "pipe",
  });
  const compiled = readFileSync(output, "utf8");
  check("compiled bg-asset 保留 CSS variable", /\.bg-asset\s*\{[^}]*rgb\(var\(--color-asset\)/s.test(compiled));
  check("compiled text-warning 保留 CSS variable", /\.text-warning\s*\{[^}]*rgb\(var\(--color-warning\)/s.test(compiled));
} catch (error) {
  check("Tailwind compilation completes", false, error instanceof Error ? error.message : String(error));
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}

if (fail > 0) {
  console.error(`\n${fail} failed, ${pass} passed`);
  process.exit(1);
}

console.log(`\n${pass} passed`);

// 2026-08-11 立：视觉语义层的行为契约。
//
// 跑法：node --experimental-strip-types scripts/test-visual-tokens.mjs
//
// 真正 import 供组件使用的映射，而非扫描 CSS 源码。这样如果某一角色
// 被错误复用成另一个角色的视觉处理，测试会直接失败。

import { getVisualTone, SOFT_TONE_OPACITIES } from "../lib/visual-system.ts";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
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

function contrastRatio(first, second) {
  const [lighter, darker] = [relativeLuminance(first), relativeLuminance(second)].sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

function blend(foreground, background, opacity) {
  return foreground.map((value, index) => Math.round(value * opacity + background[index] * (1 - opacity)));
}

function softOpacity(role) {
  const treatment = getVisualTone(role, "soft");
  const match = treatment.match(new RegExp(`bg-${role === "interaction" ? "accent" : role}/(\\d+)`));
  return match ? Number(match[1]) / 100 : null;
}

const CLASS_TOKEN_TO_ROLE = { accent: "interaction", asset: "asset", warning: "warning" };

// A compact, named contract for JSX treatments where the role-coloured surface
// is on a parent and role text is rendered by a descendant. Keeping this list
// explicit is more stable than a partial JSX parser and documents the few
// intentional nested role surfaces that must stay inside the opacity boundary.
const NESTED_ROLE_TREATMENTS = [
  {
    name: "AI suggestion container",
    path: "components/CompleteTaskModal.tsx",
    anchor: "{autoSuggestedCv && (",
    role: "interaction",
    container: /bg-accent\/(\d+)/,
    descendant: "text-[11px] text-accent",
  },
  {
    name: "commitment row",
    path: "components/MainBoard.tsx",
    anchor: 'isCommitment ? "bg-accent/',
    role: "interaction",
    container: /bg-accent\/(\d+)/,
    descendant: 'className="flex-shrink-0 text-accent text-[12px]"',
  },
];

function colorToken(role) {
  return role === "interaction" ? "accent" : role;
}

function walkCodeFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return walkCodeFiles(path);
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

function collectProductSoftTreatments() {
  const results = [];
  for (const root of ["app", "components", "lib"]) {
    for (const path of walkCodeFiles(root)) {
      const lines = readFileSync(path, "utf8").split("\n");
      lines.forEach((line, index) => {
        for (const [token, role] of Object.entries(CLASS_TOKEN_TO_ROLE)) {
          if (!line.includes(`text-${token}`)) continue;
          for (const match of line.matchAll(new RegExp(`bg-${token}/(\\d+)`, "g"))) {
            results.push({ path, line: index + 1, role, opacity: Number(match[1]) });
          }
        }
      });
    }
  }
  return results;
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

section("soft treatment contract and contrast");
for (const role of ["interaction", "asset", "warning"]) {
  const mappedOpacity = softOpacity(role);
  check(`${role} mapped soft treatment is an approved opacity`,
    mappedOpacity !== null && SOFT_TONE_OPACITIES[role].includes(mappedOpacity * 100), String(mappedOpacity));
}
const productSoftTreatments = collectProductSoftTreatments();
for (const treatment of productSoftTreatments) {
  check(`${treatment.path}:${treatment.line} ${treatment.role}/${treatment.opacity} is approved`,
    SOFT_TONE_OPACITIES[treatment.role].includes(treatment.opacity),
    JSON.stringify(treatment));
}
for (const treatment of NESTED_ROLE_TREATMENTS) {
  const source = readFileSync(treatment.path, "utf8");
  const scope = source.slice(source.indexOf(treatment.anchor));
  const container = scope.match(treatment.container);
  check(`${treatment.name} anchor exists`, source.includes(treatment.anchor));
  check(`${treatment.name} renders its role text descendant`, scope.includes(treatment.descendant));
  check(`${treatment.name} container opacity is approved`,
    container !== null && SOFT_TONE_OPACITIES[treatment.role].includes(Number(container[1])),
    container?.[1] ?? "no matching role container");
}

// The achievement flash has an intentional parent accent surface. Its small
// +1 badge must not add a second accent fill: that compound surface is too dark
// for 10px accent text in dark mode. Model a missing badge fill as 0% so this
// stays a composited-behaviour check after the UI adopts a border-only badge.
const spotlightSource = readFileSync("components/MainBoard.tsx", "utf8");
const spotlightStart = spotlightSource.indexOf('data-testid="achievement-spotlight"');
const spotlightScope = spotlightSource.slice(spotlightStart);
const spotlightUsesAssetTone = spotlightScope.includes('readyFlash\n              ? getVisualTone("asset")');
const flashMarker = spotlightSource.indexOf('data-testid="achievement-spotlight-flash"');
const flashTag = spotlightSource.slice(spotlightSource.lastIndexOf("<span", flashMarker), flashMarker);
const flashBadge = flashTag.match(/bg-asset\/(\d+)/);
const spotlightParentOpacity = softOpacity("asset") ?? 0;
const flashBadgeOpacity = Number(flashBadge?.[1] ?? 0) / 100;
check("achievement flash parent opacity is approved",
  spotlightUsesAssetTone && SOFT_TONE_OPACITIES.asset.includes(spotlightParentOpacity * 100),
  spotlightUsesAssetTone ? String(spotlightParentOpacity * 100) : "no asset tone");
check("achievement flash badge adds no second asset fill", flashBadge === null, flashBadge?.[1] ?? "transparent");
check("achievement flash badge uses readable foreground text", flashTag.includes("text-fg"), flashTag);
for (const [label, scope] of [["light", ":root"], ["dark", ".dark"]]) {
  const base = readRgbToken(scope, "bg-secondary");
  const asset = readRgbToken(scope, "asset");
  const foreground = readRgbToken(scope, "fg");
  const parentSurface = base && asset ? blend(asset, base, spotlightParentOpacity) : null;
  const badgeSurface = parentSurface && asset ? blend(asset, parentSurface, flashBadgeOpacity) : null;
  const ratio = badgeSurface && foreground ? contrastRatio(foreground, badgeSurface) : 0;
  check(`${label} achievement flash badge text reaches AA after nested composition`,
    Boolean(base && asset && foreground && parentSurface && badgeSurface) && ratio >= 4.5, ratio.toFixed(2));
}
for (const [label, scope] of [["light", ":root"], ["dark", ".dark"]]) {
  const surface = readRgbToken(scope, "bg");
  for (const role of ["interaction", "asset", "warning"]) {
    const tone = readRgbToken(scope, colorToken(role));
    for (const opacityPct of SOFT_TONE_OPACITIES[role]) {
      const opacity = opacityPct / 100;
      const renderedSurface = surface && tone ? blend(tone, surface, opacity) : null;
      const ratio = renderedSurface && tone ? contrastRatio(tone, renderedSurface) : 0;
      check(`${label} ${role}/${opacityPct} soft text reaches AA on its rendered surface`,
        Boolean(surface && tone) && ratio >= 4.5, ratio.toFixed(2));
    }
  }
}

section("achievement value hierarchy");
const achievementSource = readFileSync("app/achievements/page.tsx", "utf8");
check("main achievement spotlight is an asset surface", spotlightUsesAssetTone);
check("main achievement count uses asset text", spotlightScope.includes('text-[28px] font-bold tabular-nums leading-none text-asset'));
check("achievement quality signal uses asset", achievementSource.includes('BarChart3 size={13} className="text-asset"'));
check("achievement distribution uses asset", achievementSource.includes('className="h-full bg-asset/60 transition-all"'));
check("project achievement items are divider rows, not cards", achievementSource.includes('className="divide-y divide-border/70"') && achievementSource.includes('className="px-1 py-3 hover:bg-bg-tertiary/40 transition"'));
check("timeline achievement items are divider rows, not cards", achievementSource.includes('className="overflow-hidden rounded-xl border border-border bg-bg-secondary divide-y divide-border"') && achievementSource.includes('className="px-3 py-3 hover:bg-bg-tertiary/40 transition"'));

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

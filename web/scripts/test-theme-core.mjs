// 2026-08-01 立: theme-core.ts 端到端测试。
// 2026-08-23 改: cockpit v2 简化 — 单 dark 主题, 不再保留 light 模式。
//   旧测试基于"双主题翻转", v2 改成"永远 dark", 重新对齐断言。
//
// 跑法: node --experimental-strip-types web/scripts/test-theme-core.mjs

import {
  THEME_STORAGE_KEY,
  DEFAULT_THEME,
  getStoredTheme,
  setStoredTheme,
  applyTheme,
  getCurrentTheme,
  toggleTheme,
  bumpThemeVersion,
  subscribeTheme,
  getThemeVersion,
} from "../lib/theme-core.ts";

// ---------------------------------------------------------------------------
// 极简 DOM mock: document / window / localStorage
// ---------------------------------------------------------------------------
class ClassList {
  constructor() {
    this._set = new Set();
  }
  add(c) { this._set.add(c); }
  remove(c) { this._set.delete(c); }
  contains(c) { return this._set.has(c); }
  toArray() { return Array.from(this._set); }
}

function makeElement() {
  return {
    classList: new ClassList(),
    attributes: new Map(),
    setAttribute(name, value) { this.attributes.set(name, value); },
    getAttribute(name) { return this.attributes.get(name) ?? null; },
  };
}

const mockElement = makeElement();

globalThis.document = {
  get documentElement() { return mockElement; },
};
globalThis.window = {};

// localStorage mock: 允许测试 get 抛错 (模拟 quota / 隐私模式)
function makeLocalStorage({ throwOnGet = false } = {}) {
  const store = new Map();
  return {
    getItem(k) {
      if (throwOnGet) throw new Error("mock quota exceeded");
      return store.has(k) ? store.get(k) : null;
    },
    setItem(k, v) {
      store.set(k, String(v));
    },
    removeItem(k) {
      store.delete(k);
    },
    clear() {
      store.clear();
    },
  };
}

globalThis.window = globalThis.window || {};
window.localStorage = makeLocalStorage();

// ---------------------------------------------------------------------------
// 断言工具
// ---------------------------------------------------------------------------
let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`  ✓ ${name}`); }
  else { fail++; console.log(`  ✗ ${name}${detail ? ` — ${detail}` : ""}`); }
}
function section(name) { console.log(`\n# ${name}`); }

// 重置 element + storage (用例间隔离)
function reset({ theme = null, throwOnGet = false } = {}) {
  mockElement.classList = new ClassList();
  mockElement.attributes = new Map();
  window.localStorage = makeLocalStorage({ throwOnGet });
  if (theme) {
    mockElement.classList.add(theme);
    mockElement.setAttribute("data-theme", theme);
  }
  window.localStorage.removeItem(THEME_STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// v2 用例 (单 dark 主题 — 所有函数都返/写 "dark", 不再有 light 概念)
// ---------------------------------------------------------------------------

section("v2: getStoredTheme 永远返 'dark' (兼容老数据 'light')");
reset();
check("空 localStorage 返默认 (dark)", getStoredTheme() === "dark",
  `实际: ${getStoredTheme()}`);
window.localStorage.setItem(THEME_STORAGE_KEY, "light");
check("localStorage 存 'light' 也返 'dark' (兼容)",
  getStoredTheme() === "dark", `实际: ${getStoredTheme()}`);
window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
check("localStorage 存 'dark' 返 'dark'",
  getStoredTheme() === "dark");

section("v2: setStoredTheme 永远写 'dark'");
reset();
setStoredTheme("light"); // 传 light 也会被忽略
check("setStoredTheme('light') 实际写 'dark'",
  window.localStorage.getItem(THEME_STORAGE_KEY) === "dark",
  `实际: ${window.localStorage.getItem(THEME_STORAGE_KEY)}`);
setStoredTheme("dark");
check("setStoredTheme('dark') 写 'dark'",
  window.localStorage.getItem(THEME_STORAGE_KEY) === "dark");

section("v2: getStoredTheme 容错 (非法值/空)");
reset();
window.localStorage.setItem(THEME_STORAGE_KEY, "rainbow");
check("非法值 (rainbow) 返默认", getStoredTheme() === "dark",
  `实际: ${getStoredTheme()}`);
window.localStorage.setItem(THEME_STORAGE_KEY, "");
check("空字符串返默认", getStoredTheme() === "dark");

section("v2: applyTheme 永远设 .dark, 移除 .light");
reset();
mockElement.classList.add("light");
applyTheme("dark");
check("applyTheme 永远加 .dark class",
  mockElement.classList.contains("dark"));
check("applyTheme 永远移除 .light class",
  !mockElement.classList.contains("light"));
check("applyTheme data-theme=dark",
  mockElement.getAttribute("data-theme") === "dark");

section("v2: getCurrentTheme 永远返 'dark'");
reset();
mockElement.classList.add("light");
mockElement.setAttribute("data-theme", "light");
check("DOM data-theme=light 也返 'dark' (v2 永远 dark)",
  getCurrentTheme() === "dark");
reset();
check("空 DOM 返 'dark'", getCurrentTheme() === "dark");

section("v2: toggleTheme 是 no-op, 永远返 'dark'");
reset();
check("toggleTheme 返 'dark'",
  toggleTheme() === "dark");
check("toggleTheme 多次都返 'dark'",
  toggleTheme() === "dark" && toggleTheme() === "dark");
// 注: v2 的 toggleTheme 是 no-op, 不写 localStorage (因为没有"另一主题"可切)。
// 持久化由 setStoredTheme("dark") 单独负责, 不在 toggle 副作用里。
check("toggleTheme 不动 localStorage (no-op, 没副作用)",
  window.localStorage.getItem(THEME_STORAGE_KEY) === null);

section("subscribe / bumpThemeVersion 订阅 (跟 v2 兼容)");
reset();
let notifyCount = 0;
const unsub = subscribeTheme(() => notifyCount++);
check("订阅后立即不被通知", notifyCount === 0);
const v0 = getThemeVersion();
bumpThemeVersion();
check("bump 1 次通知 +1", notifyCount === 1);
check("version +1", getThemeVersion() === v0 + 1);
bumpThemeVersion();
bumpThemeVersion();
bumpThemeVersion();
check("bump 4 次累计通知 +4 (1 初始 + 3 后续)", notifyCount === 4);
check("version +4 (v0+4)", getThemeVersion() === v0 + 4);
unsub();
bumpThemeVersion();
check("unsub 后不再通知 (仍 4)", notifyCount === 4);
check("version 仍 +5", getThemeVersion() === v0 + 5);

section("SSR 安全 (typeof window === 'undefined')");
let didThrow = false;
try { getStoredTheme(); } catch { didThrow = true; }
check("有 window 时 getStoredTheme 不抛", !didThrow);

section("localStorage 抛错容错 (get quota exceeded)");
reset({ throwOnGet: true });
const gotDespiteThrow = getStoredTheme();
check("localStorage getItem 抛错时 getStoredTheme 走 catch 返默认",
  gotDespiteThrow === DEFAULT_THEME, `实际: ${gotDespiteThrow}`);

let setThrew = false;
try { setStoredTheme("dark"); } catch { setThrew = true; }
check("setStoredTheme 不抛", !setThrew);

reset({ throwOnGet: false });
setStoredTheme("dark");
check("setStoredTheme 正常路径能写能读",
  getStoredTheme() === "dark");

// ---------------------------------------------------------------------------
// 总结
// ---------------------------------------------------------------------------
console.log(`\n=== ${pass} passed, ${fail} failed ===`);
if (fail > 0) {
  process.exit(1);
}

// 2026-08-01 立: theme-core.ts 端到端测试。
//
// 跑法: node --experimental-strip-types web/scripts/test-theme-core.mjs
//
// 真实 import lib/theme-core.ts (无 React 依赖), 手写极简 DOM mock
// (document / window / localStorage), 验证所有纯函数行为真实可工作。
//
// 不锁退化 (静态不变量测试在 app/tests/test_theme_toggle_invariants.py),
// 这里只锁"真能跑 + 行为对", 是 lesson #2 末尾"每加 LLM 端点都要端到端
// 实测" 的同源教训 — 加工具/函数 端到端实测是必做的, 不是 nice-to-have。

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
//
// 设计: setItem 永远成功 (源码 try/catch 包住, 不影响主流程),
// getItem 在指定条件下抛错模拟读取受限; 验证源码 catch 能兜住。
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

// 关键: 源码用 window.localStorage, 不是 globalThis.localStorage。
// mock 必须装到 window.localStorage, 否则 source code 看不到。
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
    if (theme === "dark") {
      mockElement.classList.add("dark");
    } else {
      mockElement.classList.add("light");
    }
    mockElement.setAttribute("data-theme", theme);
  }
  // 清掉 localStorage
  window.localStorage.removeItem(THEME_STORAGE_KEY);
}

// ---------------------------------------------------------------------------
// 用例
// ---------------------------------------------------------------------------
section("getStoredTheme / setStoredTheme roundtrip");
reset();
check("空 localStorage 返默认 (dark)", getStoredTheme() === DEFAULT_THEME,
  `实际: ${getStoredTheme()}`);
setStoredTheme("light");
check("setStoredTheme('light') 后 get 返 light", getStoredTheme() === "light");
setStoredTheme("dark");
check("setStoredTheme('dark') 后 get 返 dark", getStoredTheme() === "dark");

section("getStoredTheme 容错");
reset();
// 写入非法值, 模拟旧版本/外部脚本污染
window.localStorage.setItem(THEME_STORAGE_KEY, "rainbow");
check("非法值 (rainbow) 返默认", getStoredTheme() === DEFAULT_THEME,
  `实际: ${getStoredTheme()}`);
window.localStorage.setItem(THEME_STORAGE_KEY, "");
check("空字符串返默认", getStoredTheme() === DEFAULT_THEME);

section("applyTheme 切 class + data-theme");
reset();
applyTheme("light");
check("applyTheme('light') 加 .light class",
  mockElement.classList.contains("light"));
check("applyTheme('light') 移除 .dark class",
  !mockElement.classList.contains("dark"));
check("applyTheme('light') data-theme=light",
  mockElement.getAttribute("data-theme") === "light");

applyTheme("dark");
check("applyTheme('dark') 加 .dark class",
  mockElement.classList.contains("dark"));
check("applyTheme('dark') 移除 .light class",
  !mockElement.classList.contains("light"));
check("applyTheme('dark') data-theme=dark",
  mockElement.getAttribute("data-theme") === "dark");

section("applyTheme 互斥 (light + dark 不共存)");
reset();
applyTheme("light");
applyTheme("dark");
check("连续切到 dark 后只剩 .dark",
  mockElement.classList.contains("dark") && !mockElement.classList.contains("light"));

section("getCurrentTheme 读 DOM");
reset({ theme: "light" });
check("DOM data-theme=light 时 getCurrentTheme 返 light",
  getCurrentTheme() === "light");
reset({ theme: "dark" });
check("DOM data-theme=dark 时 getCurrentTheme 返 dark",
  getCurrentTheme() === "dark");
reset();
check("空 DOM 返默认", getCurrentTheme() === DEFAULT_THEME);

section("toggleTheme 翻转");
reset({ theme: "dark" });
const after1 = toggleTheme();
check("dark → toggle 后变 light", after1 === "light");
check("DOM 也变 light", mockElement.classList.contains("light"));
check("localStorage 也存 light", getStoredTheme() === "light");

reset({ theme: "light" });
const after2 = toggleTheme();
check("light → toggle 后变 dark", after2 === "dark");
check("DOM 也变 dark", mockElement.classList.contains("dark"));
check("localStorage 也存 dark", getStoredTheme() === "dark");

section("subscribe / bumpThemeVersion 订阅");
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
// 注意: 真 SSR 测试需要清掉 globalThis.window, 但本测试也要它, 跳过
// 已经在源码注释里说明, 这里只断"window 存在时能用"
let didThrow = false;
try { getStoredTheme(); } catch { didThrow = true; }
check("有 window 时 getStoredTheme 不抛", !didThrow);

section("localStorage 抛错容错 (get quota exceeded)");
// get 抛错时, getStoredTheme 应走 catch 返默认主题
reset({ throwOnGet: true });
const gotDespiteThrow = getStoredTheme();
check("localStorage getItem 抛错时 getStoredTheme 走 catch 返默认",
  gotDespiteThrow === DEFAULT_THEME, `实际: ${gotDespiteThrow}`);

// set 不会抛 (mock 永远成功), 但源码 try/catch 也兜得住
let setThrew = false;
try { setStoredTheme("light"); } catch { setThrew = true; }
check("setStoredTheme 不抛", !setThrew);

// 切到 throwOnGet=false 后, set 的值能正常读到
reset({ throwOnGet: false });
setStoredTheme("light");
check("setStoredTheme 正常路径能写能读", getStoredTheme() === "light");

section("完整循环: dark → toggle → toggle → 应回到 dark");
reset({ theme: "dark" });
toggleTheme();
toggleTheme();
check("dark → toggle ×2 后回到 dark",
  getCurrentTheme() === "dark" && getStoredTheme() === "dark");

// ---------------------------------------------------------------------------
// 总结
// ---------------------------------------------------------------------------
console.log(`\n=== ${pass} passed, ${fail} failed ===`);
if (fail > 0) {
  process.exit(1);
}

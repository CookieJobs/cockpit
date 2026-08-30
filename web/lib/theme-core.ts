// 2026-08-23 改: cockpit v2 — 单 dark 主题, 不再保留 light 模式。
//
// 改动要点:
//   - Theme 类型从 "light" | "dark" 改成 const "dark" (光杆 "dark" string)
//   - getStoredTheme 永远返回 "dark" (保留 localStorage key 兼容老用户数据)
//   - applyTheme 永远加 .dark, 不再切 .light
//   - toggleTheme 抛错 (不应该再被调用, 但保留函数避免 break 外部 import)
//
// 留 localStorage 读 + 兼容的原因: 老用户 localStorage 里可能有 "light" 值,
//   早期同步脚本 (layout.tsx) 也兼容 "light" → 当 dark 处理即可, 不报错。

export type Theme = "dark";

export const THEME_STORAGE_KEY = "cockpit_theme";
export const DEFAULT_THEME: Theme = "dark";

/** 读 localStorage 主题, v2 永远返 "dark"。保留函数签名兼容外部 import。 */
export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  // 兼容老数据: 读到 "light" 也当 "dark" 处理, 不动用户已存的值
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return DEFAULT_THEME;
  } catch {
    // localStorage 不可用 (隐私模式), 走默认
  }
  return DEFAULT_THEME;
}

/** 写 localStorage 主题, v2 永远写 "dark"。保留函数签名兼容。 */
export function setStoredTheme(_theme: Theme): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
  } catch {
    // ignore
  }
}

/**
 * 应用 dark 主题到 DOM。v2 永远加 .dark class, 不切 .light。
 * 早期同步脚本 (layout.tsx) 也会做同样事, 这里运行时切换留作 0 操作
 * (因为 v2 没有其他主题可切)。
 */
export function applyTheme(_theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.add("dark");
  root.classList.remove("light");
  root.setAttribute("data-theme", "dark");
}

/** 从 DOM 读当前主题, v2 永远返 "dark"。 */
export function getCurrentTheme(): Theme {
  return DEFAULT_THEME;
}

/**
 * 翻转主题。v2 单 dark 模式, 翻转无意义但保留函数签名避免 break。
 * 返回当前主题 (永远是 "dark")。
 */
export function toggleTheme(): Theme {
  return DEFAULT_THEME;
}

// ---------------------------------------------------------------------------
// 简单发布订阅: useTheme 订阅源, applyTheme / storage 事件触发 +1
// 2026-08-23: 保留版本号机制, 但实际不会再变 (主题永远 dark)
// ---------------------------------------------------------------------------

let themeVersion = 0;
const themeListeners = new Set<() => void>();

export function bumpThemeVersion() {
  themeVersion += 1;
  themeListeners.forEach((fn) => fn());
}

export function subscribeTheme(fn: () => void) {
  themeListeners.add(fn);
  return () => {
    themeListeners.delete(fn);
  };
}

export function getThemeVersion(): number {
  return themeVersion;
}

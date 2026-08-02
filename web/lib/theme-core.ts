// 2026-08-01 立: 主题纯函数 (无 React 依赖), 方便 mjs 端到端测。
//
// 拆 lib/theme.ts 的原因:
//   - lib/theme.ts 含 useSyncExternalStore / useCallback 等 React hook,
//     Node 22 直接跑不到 (即使用 --experimental-strip-types 也不行, 因为
//     需要 react runtime)
//   - 把纯函数 (getStoredTheme / setStoredTheme / applyTheme / getCurrentTheme
//     / toggleTheme / 订阅) 抽到这里, mjs 端到端能 import 跑真实验证。
//   - React 副作用 (useTheme hook) 留在 lib/theme.ts, 只在 Next.js 环境用。

export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "cockpit_theme";
export const DEFAULT_THEME: Theme = "dark";

/** 读 localStorage 主题, 无效或缺失返默认。客户端用, server 用返默认。 */
export function getStoredTheme(): Theme {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage 不可用 (隐私模式), 走默认
  }
  return DEFAULT_THEME;
}

/** 写 localStorage 主题, 不可用时静默失败。 */
export function setStoredTheme(theme: Theme): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // ignore
  }
}

/**
 * 应用主题到 DOM: 切 html class + data-theme attr。
 * 早期同步脚本 (layout.tsx) 已经设过, 这里做运行时切换用。
 * 跟早期脚本逻辑保持一致: dark 加 .dark, light 加 .light, 互斥。
 */
export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
    root.classList.remove("light");
  } else {
    root.classList.add("light");
    root.classList.remove("dark");
  }
  root.setAttribute("data-theme", theme);
}

/** 从 DOM 读当前主题 (早期脚本写过的)。客户端用。 */
export function getCurrentTheme(): Theme {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  // 兜底: 早期脚本可能因为异常没设, 看 class
  if (document.documentElement.classList.contains("light")) return "light";
  return DEFAULT_THEME;
}

/** 翻转当前主题并应用, 返新主题。 */
export function toggleTheme(): Theme {
  const next: Theme = getCurrentTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  setStoredTheme(next);
  return next;
}

// ---------------------------------------------------------------------------
// 简单发布订阅: useTheme 订阅源, applyTheme / storage 事件触发 +1
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

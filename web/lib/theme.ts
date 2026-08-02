"use client";

// 2026-08-01 立: 主题 React hook (useTheme)。
//
// 纯函数 (getStoredTheme / setStoredTheme / applyTheme / getCurrentTheme /
// toggleTheme / 订阅源) 在 lib/theme-core.ts, 这个文件只做:
//   1) re-export 纯函数 (向后兼容, 其它文件 import { useTheme } from
//      '@/lib/theme' 仍能拿到)
//   2) useTheme hook 用 useSyncExternalStore 订阅 theme-core 的版本号
//
// 多 tab 同步: 监听 localStorage 'storage' 事件, 其他 tab 切了主题
// 这边也跟切。

import { useSyncExternalStore, useCallback } from "react";
import {
  type Theme,
  THEME_STORAGE_KEY,
  DEFAULT_THEME,
  getStoredTheme,
  setStoredTheme,
  applyTheme,
  getCurrentTheme,
  bumpThemeVersion,
  subscribeTheme,
} from "./theme-core";

export type { Theme };
export {
  THEME_STORAGE_KEY,
  DEFAULT_THEME,
  getStoredTheme,
  setStoredTheme,
  applyTheme,
  getCurrentTheme,
};

// 跨 tab 同步: 在 module 加载时注册一次, 全局唯一监听。
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== THEME_STORAGE_KEY) return;
    const newTheme = getStoredTheme();
    const current = getCurrentTheme();
    if (newTheme !== current) {
      applyTheme(newTheme);
      bumpThemeVersion();
    }
  });
}

function getThemeSnapshot(): Theme {
  return getCurrentTheme();
}

function getThemeServerSnapshot(): Theme {
  // SSR: 返默认主题, 早期同步脚本在 client mount 时覆盖。
  return DEFAULT_THEME;
}

export function useTheme() {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getThemeServerSnapshot,
  );

  const setTheme = useCallback((next: Theme) => {
    applyTheme(next);
    setStoredTheme(next);
    bumpThemeVersion();
  }, []);

  const toggle = useCallback(() => {
    return setTheme(theme === "dark" ? "light" : "dark");
  }, [theme, setTheme]);

  return { theme, setTheme, toggle } as const;
}

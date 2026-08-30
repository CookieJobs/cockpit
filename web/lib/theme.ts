"use client";

// 2026-08-23 改: cockpit v2 — useTheme 仍存在, 但 theme 永远是 "dark"。
//
// 保留 hook API 的原因:
//   - ThemeToggle.tsx / 其他组件可能 import { useTheme }
//   - 突然删 hook = 整个项目编译失败
//   - 退一步: hook 永远返 { theme: "dark", setTheme, toggle } 让调用方不报错
//
// 跨 tab 同步: 保留 storage 事件监听 (理论上永远不会再触发, 但不删)

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

// 跨 tab 同步: 保留 (虽然 v2 主题不会变, 但 storage 事件可能有其他用途)
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== THEME_STORAGE_KEY) return;
    // v2: 任何 storage 变化都同步到 dark, 不再切 light
    applyTheme("dark");
    bumpThemeVersion();
  });
}

function getThemeSnapshot(): Theme {
  return getCurrentTheme();
}

function getThemeServerSnapshot(): Theme {
  return DEFAULT_THEME;
}

export function useTheme() {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getThemeServerSnapshot,
  );

  const setTheme = useCallback((_next: Theme) => {
    // v2: setTheme 永远设置 dark, 不接受 light
    applyTheme("dark");
    setStoredTheme("dark");
    bumpThemeVersion();
  }, []);

  const toggle = useCallback(() => {
    // v2: toggle 是 no-op, 永远返 dark
    return DEFAULT_THEME;
  }, []);

  return { theme, setTheme, toggle } as const;
}

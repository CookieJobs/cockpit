"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/lib/theme";

/**
 * 2026-08-01 立: 主题切换按钮 (顶栏 IconButton)。
 *
 * 行为:
 *   - 显示当前主题的"反向图标" — dark 模式显示 ☀️ (提示"点我切到亮"),
 *     light 模式显示 🌙 (提示"点我切到暗")。这是 macOS / iOS 通用约定。
 *   - click 调 useTheme().toggle(), 立即:
 *     1) applyTheme() 切 html class (CSS variables 自动换, 全页过渡)
 *     2) setStoredTheme() 写 localStorage (跨刷新保留)
 *     3) bumpVersion() 触发 useSyncExternalStore 订阅者重渲 (icon 切换)
 *   - 多 tab 同步: lib/theme.ts 里的 'storage' 事件监听让其他 tab 跟切。
 *
 * 设计决定:
 *   - 不用 dropdown / 三态 (light/dark/system): 简化 UX, 一键够用, 跟
 *     "StatusMenu" / "PriorityMenu" 多 popover 风格不冲突。
 *   - 不用 emoji ☀️/🌙 用 lucide Sun/Moon: 跟整站 icon 语言一致
 *     (Settings / Calendar / Sparkles 都是 lucide), 视觉协调。
 *   - size 14: 跟 Settings icon 同一尺寸, 视觉权重一致。
 *   - 16x16 button + hover bg-bg-tertiary: 跟 Settings link 同款 "hover 提示"
 *     风格, 不引入新视觉模式。
 *   - aria-label 跟 title 同步: 屏幕阅读器 + hover tooltip 同源信息。
 */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggle}
      title={isDark ? "切换到白天模式" : "切换到黑夜模式"}
      aria-label={isDark ? "切换到白天模式" : "切换到黑夜模式"}
      data-testid="theme-toggle"
      data-theme-state={theme}
      className="text-fg-muted hover:text-fg transition p-1.5 rounded hover:bg-bg-tertiary"
    >
      {isDark ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}

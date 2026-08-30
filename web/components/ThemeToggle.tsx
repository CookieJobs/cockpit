"use client";

import { Moon } from "lucide-react";

/**
 * 2026-08-23 改: cockpit v2 — 单 dark 主题, ThemeToggle 改成只读指示器。
 *
 * 原因:
 *   - v1 双主题, ThemeToggle 是 Sun/Moon 切换按钮
 *   - v2 单 dark, 切换没意义, 但保留一个 Moon icon 让用户知道"当前是 dark 模式"
 *     (跟其他 nav icon 视觉一致, 不会让用户觉得代码坏了)
 *
 * 不再是 button, 改成 div, 无 hover 状态, 无点击, 无 tooltip。
 */
export function ThemeToggle() {
  return (
    <span
      className="text-fg-muted p-1.5 rounded inline-flex items-center"
      title="当前是深色模式"
      aria-label="当前是深色模式"
      data-testid="theme-indicator"
      data-theme-state="dark"
    >
      <Moon size={14} />
    </span>
  );
}

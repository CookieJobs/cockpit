"use client";

/**
 * usePopover — 共享的 popover 状态机 (2026-07-22 立)。
 *
 * 背景：StatusMenu / PriorityMenu 两个组件 (MainBoard.tsx) 各有 ~30 行
 * 几乎一字不差的 useState(open) + useRef + click-outside 监听 + Esc 监听
 * + focus 回到 trigger 的样板代码。重复的 30 行 × 2 = 60 行, 改一个
 * 可达性细节要改两处。
 *
 * 这个 hook 抽走所有"开/关/点外面/Esc"行为, 调用方只需:
 *   1. 拿 { open, toggle, close, containerRef, triggerRef } 状态
 *   2. 把 containerRef 套外层 div, triggerRef 套触发 button
 *   3. open 时渲染 popover 内容 (children)
 *
 * 调用方仍然完全控制:
 * - 触发 button 的视觉 (色点/横条/图标)
 * - popover 内容的渲染 (列表项/分隔线/特殊项)
 * - onChange/onComplete 等业务 callback
 *
 * 不变量: 此 hook 跟原 StatusMenu/PriorityMenu 内联实现**逐行等价** —
 *   - mousedown 检测外部点击 (不是 click, 避免 button 内部点击误触关闭)
 *   - Esc 关闭 + focus 回到 trigger (基础可达性)
 *   - 关闭后 setOpen(false) 触发重新 render, popover 消失
 *
 * 命名沿用 StatusMenu 原有的 "open / setOpen / buttonRef" 风格, 减少 diff 噪音。
 */

import { useState, useRef, useEffect } from "react";

export interface UsePopoverResult {
  open: boolean;
  setOpen: (v: boolean | ((o: boolean) => boolean)) => void;
  toggle: () => void;
  close: () => void;
  // React 18 的 useRef<T>(null) 返回 RefObject<T> (不带 null), 所以这里也不带
  containerRef: React.RefObject<HTMLDivElement>;
  triggerRef: React.RefObject<HTMLButtonElement>;
}

export function usePopover(): UsePopoverResult {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // click outside 关闭 (mousedown 不是 click, 避免 button 内部点击冒泡误触)
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Esc 关闭 + focus 回到 trigger (基础可达性)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  return {
    open,
    setOpen,
    toggle: () => setOpen((o) => !o),
    close: () => setOpen(false),
    containerRef,
    triggerRef,
  };
}

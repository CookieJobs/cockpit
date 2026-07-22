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
 *   1. 拿 { open, toggle, close, containerRef, triggerRef, popoverRef } 状态
 *   2. 把 containerRef 套外层 div, triggerRef 套触发 button
 *   3. 把 popoverRef 套 popover 根元素 (在 Portal 模式下也用, 让 click-outside
 *      检测不会"自己点自己 = 关闭")
 *   4. open 时渲染 popover 内容 (children)
 *
 * (2026-07-22 加 popoverRef): 之前 click-outside 只检测 containerRef,
 *   在 Portal 模式下 popover 在 body 下不在 containerRef 子树, 点 popover
 *   内部会被误判为"外部点击"而关闭。加 popoverRef 解决。
 *
 * 调用方仍然完全控制:
 * - 触发 button 的视觉 (色点/横条/图标)
 * - popover 内容的渲染 (列表项/分隔线/特殊项)
 * - 定位方式 (absolute / Portal+fixed, 配合 usePopoverPosition)
 * - onChange/onComplete 等业务 callback
 *
 * 不变量: 此 hook 跟原 StatusMenu/PriorityMenu 内联实现**逐行等价** —
 *   - mousedown 检测外部点击 (不是 click, 避免 button 内部点击误触关闭)
 *   - Esc 关闭 + focus 回到 trigger (基础可达性)
 *   - 关闭后 setOpen(false) 触发重新 render, popover 消失
 *
 * 命名沿用 StatusMenu 原有的 "open / setOpen / buttonRef" 风格, 减少 diff 噪音。
 */

import { useState, useRef, useEffect, useLayoutEffect } from "react";

export interface UsePopoverResult {
  open: boolean;
  setOpen: (v: boolean | ((o: boolean) => boolean)) => void;
  toggle: () => void;
  close: () => void;
  // React 18 的 useRef<T>(null) 返回 RefObject<T> (不带 null), 所以这里也不带
  containerRef: React.RefObject<HTMLDivElement>;
  triggerRef: React.RefObject<HTMLButtonElement>;
  /** popover 根元素 ref — Portal 模式下必传, 让 click-outside 不会"自己点自己 = 关闭" */
  popoverRef: React.RefObject<HTMLDivElement>;
}

export function usePopover(): UsePopoverResult {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // click outside 关闭 (mousedown 不是 click, 避免 button 内部点击冒泡误触)
  // containerRef (trigger 外层) + popoverRef (Portal 渲染的 popover 根) 都不算"外部"
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (containerRef.current?.contains(target)) return;
      if (popoverRef.current?.contains(target)) return;
      setOpen(false);
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
    popoverRef,
  };
}


/**
 * usePopoverPosition — Portal 模式下计算 popover 的 fixed 位置 (2026-07-22 立)。
 *
 * 背景：StatusMenu / PriorityMenu 之前用 `absolute left-0 top-6` 定位 popover,
 *   相对 trigger 容器。但当 trigger 在 ProjectCard (overflow-hidden) 内部底部
 *   时, popover 向下展开会被 ProjectCard 的 overflow-hidden **裁掉** —
 *   CSS 的 overflow-hidden 无视 z-index 直接裁切超出 box 边界的内容。
 *
 * 修法：popover 改用 React Portal 渲染到 document.body, 配合 position: fixed
 *   (相对视口定位, 跳出任何 overflow / stacking context 限制)。
 *
 * 用法:
 *   const pop = usePopover();
 *   const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 4 });
 *   {pop.open && createPortal(
 *     <div ref={pop.popoverRef} style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: 50 }}>
 *       ...
 *     </div>,
 *     document.body
 *   )}
 *
 * 行为:
 * - 关闭时不计算位置 (返回上一次值, 但不影响 — popover 不渲染)
 * - 打开时立刻 (useLayoutEffect) 计算位置, 避免一帧闪烁
 * - 监听 triggerRef 父级滚动 + window resize, 重新计算位置
 *   (capture phase 监听滚动才能捕获嵌套滚动容器的滚动事件)
 * - 滚动时让 popover 跟随 trigger 移动 (而不是直接关闭) — UX 更稳:
 *   用户在 list 里滚动浏览时, 已经打开的 popover 应该跟着 trigger 走
 *
 * 命名: 跟 React 生态里 floating-ui / radix-ui 的 useFloating 同名但功能更轻量。
 */
export interface UsePopoverPositionOptions {
  /** popover 跟 trigger 顶部的额外间距, 默认 4px */
  offsetY?: number;
  /** popover 跟 trigger 左边的额外间距, 默认 0 */
  offsetX?: number;
  /** z-index, 默认 50 (在 ProjectCard / overlay 之上) */
  zIndex?: number;
}

export interface PopoverPosition {
  top: number;
  left: number;
  zIndex: number;
}

export function usePopoverPosition(
  triggerRef: React.RefObject<HTMLElement>,
  open: boolean,
  options: UsePopoverPositionOptions = {}
): PopoverPosition {
  const { offsetY = 4, offsetX = 0, zIndex = 50 } = options;
  const [pos, setPos] = useState<PopoverPosition>({ top: 0, left: 0, zIndex });

  // 用 useLayoutEffect 同步计算位置, 避免 popover 弹出后先在 (0,0) 闪一帧
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const update = () => {
      const rect = triggerRef.current!.getBoundingClientRect();
      setPos({ top: rect.bottom + offsetY, left: rect.left + offsetX, zIndex });
    };
    update();
    // capture: true 才能监听到嵌套 overflow 容器的滚动事件
    window.addEventListener("scroll", update, { capture: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, { capture: true });
      window.removeEventListener("resize", update);
    };
  }, [open, offsetY, offsetX, zIndex, triggerRef]);

  return pos;
}

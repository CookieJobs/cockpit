"use client";

/**
 * ProjectEmojiPicker — 项目 emoji 选择器 (2026-08-11 立)。
 *
 * 设计要点:
 * 1. **范围限定 50 emoji 池子** (从 lib/projectEmojis 复用)
 *    - 跟原有确定性 emoji 视觉一致
 *    - 故意不开全量 emoji 选择器 (lesson #15 同款反模式: 选项过多 = 完成率下降)
 *
 * 2. **3 个操作入口**:
 *    - 50 emoji 网格: 直接选
 *    - "当前 hash: X" 可点 button: 恢复成 hash 兜底
 *    - "🎲 随机": 抽一个 (避重复选当前)
 *
 * 3. **不主动关闭** (v3 立): 选了 emoji / 切 hash / 随机 都不关 picker,
 *    用户可连续微调。只有 click-outside 或 Esc 才关 (走 usePopover 默认行为)。
 *    跟 Notion emoji picker 行为一致。
 *
 * 4. **复用 usePopover + usePopoverPosition + createPortal**
 *    - 跟 StatusMenu / PriorityMenu / DueEditor 同根
 *    - Portal 跳出 ProjectCard overflow-hidden 裁切
 *    - click-outside + Esc 关闭 + focus 回到 trigger 全部白嫖
 *
 * 5. **hover 视觉** (v5 重做, AI CTO 反思):
 *    - 跟整个 app 的 hover 语言保持一致: subtle bg change + 1px border
 *    - 不要 scale、不要 box-shadow、不要 accent 撞色
 *    - 之前 v3/v4 我套的是 "scale + box-shadow + accent ring + bg" 四件套,
 *      跟 TaskRow / StatusMenu / 归档按钮的 "bg change" 模式完全不一致,
 *      在视觉上是个闯入者。这次全部回退到跟 StatusMenu 一档的克制度。
 *    - emoji 网格 hover 收成纯 bg 切换, 当前选中态用 bg-accent/20 + ring-accent/50
 *    - 整个 popover 加 .popover-in 动画 (scale + fade 复合, 150ms) 保留
 *
 * 6. **关闭行为** (v4 强化保留):
 *    - 内部 button 双重 stopPropagation (onClick + onMouseDown) 保留
 *    - 顶 div 也 stopPropagation 兜底 (mousedown capture 阶段)
 *
 * 2026-08-12 v6 调整 (用户反馈 hover 太丑):
 *   - 原生 title tooltip 是 OS 级灰底黑箭头框, 跟 app 设计语言完全不搭,
 *     还直接压在项目描述文字上 → 换成 portal 渲染的自定义 tooltip
 *     (复用 popover 设计 token, 400ms 延迟, 优先在 trigger 上方展开, 不遮内容)
 *   - trigger hover: 仅显示细圆环阴影；不填充背景、不改变尺寸，保留 emoji 本身的轻量感
 *   - 可达性: 去掉 title 后用 aria-label 保留屏幕阅读器信息
 *
 * 2026-08-12 v5 调整 (AI CTO 反思, 跟整个 app 的 hover 语言对齐):
 *   - trigger: 彻底去掉 scale/box-shadow/accent 撞色, 改用 bg-tertiary + 1px border 浮现
 *   - trigger 内的 emoji span: 不再 scale
 *   - emoji 网格: 去掉 scale-110/shadow/ring, 纯 bg 切换; 选中态收成 accent/20 + ring-accent/50
 *   - 底部按钮: 去掉 scale, 纯 bg 切换
 *   - transition 只保留 colors (去掉 transform/shadow), 更快更克制
 *
 * 2026-08-12 v4 调整 (推翻, 见 v5):
 *   - trigger 用 box-shadow 真圆环 (rounded-full 跟 accent 撞色丑)
 *   - emoji 网格 scale-110 + shadow-md + ring-accent/30 (跟 app 整体 hover 不一致)
 *   - 顶 div 加 onMouseDownCapture 兜底 (保留)
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { usePopover, usePopoverPosition } from "./Popover";
import { PROJECT_EMOJIS } from "@/lib/projectEmojis";

export interface ProjectEmojiPickerProps {
  /** 用户当前手动选的 emoji; null = 用 hash 兜底 (回退状态) */
  value: string | null;
  /** 项目 id 算出的 hash emoji, 供 picker 底部"当前 hash" 按钮用 (点了恢复) */
  hashEmoji: string;
  /** 选择回调: emoji 字符串 (选了某个或恢复 hash 那个)。
   *  v3: 选完不再关 picker, 由 usePopover 的 click-outside / Esc 统一处理关闭。 */
  onChange: (emoji: string) => void;
  /** 触发 button 的 children (调用方控制视觉, 通常是 <span>{emoji}</span>) */
  children: React.ReactNode;
}

export function ProjectEmojiPicker({
  value,
  hashEmoji,
  onChange,
  children,
}: ProjectEmojiPickerProps) {
  const pop = usePopover();
  // zIndex 60: 比其它 popover (StatusMenu/PriorityMenu 50) 高一档,
  // 防止项目卡片内部的 button 在某些 stacking context 下盖过 picker
  const pos = usePopoverPosition(pop.triggerRef, pop.open, { offsetY: 6, zIndex: 60 });
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // v6: 自定义 tooltip (替代原生 title) — 400ms 延迟浮现, 优先在 trigger 上方,
  // 上方空间不够 (视口顶部) 时翻到下方。portal 渲染跳出 ProjectCard overflow-hidden。
  const [tip, setTip] = useState<{ top: number; left: number; above: boolean } | null>(null);
  const tipTimer = useRef<number | null>(null);
  const clearTipTimer = () => {
    if (tipTimer.current !== null) {
      window.clearTimeout(tipTimer.current);
      tipTimer.current = null;
    }
  };
  const showTipSoon = () => {
    clearTipTimer();
    tipTimer.current = window.setTimeout(() => {
      const el = pop.triggerRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      // 上方至少留 36px (tooltip 高 ~24px + 间距), 否则翻到下方
      const above = rect.top > 36;
      setTip({
        top: above ? rect.top - 6 : rect.bottom + 6,
        left: rect.left + rect.width / 2,
        above,
      });
    }, 400);
  };
  const hideTip = () => {
    clearTipTimer();
    setTip(null);
  };
  useEffect(() => clearTipTimer, []);

  // v3: 不再 pop.close() — 让用户连续微调, 由 usePopover 的 click-outside / Esc 统一关闭
  const selectEmoji = (emoji: string) => {
    if (value !== emoji) onChange(emoji);
  };

  const pickRandom = () => {
    // 避重复: 如果池子里只有一个 emoji (极端小池子), 退化为直接选第一个
    const pool = PROJECT_EMOJIS.length > 1 ? PROJECT_EMOJIS : [PROJECT_EMOJIS[0]];
    const candidates = pool.filter((e) => e !== value);
    const pick = candidates[Math.floor(Math.random() * candidates.length)];
    selectEmoji(pick);
  };

  // v4: capture 阶段在 popover 根 div 上拦截 mousedown, 彻底挡掉
  // 来自 popover 内部的冒泡到 document 的事件 (usePopover 的 outside 检测
  // 走 document mousedown, 双重保险避免在某些 React 18 委托边缘情况下漏掉)
  const swallow = (e: React.SyntheticEvent) => e.stopPropagation();

  return (
    <>
      <button
        ref={pop.triggerRef}
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          hideTip();
          pop.toggle();
        }}
        onMouseDown={(e) => e.stopPropagation()}
        onMouseEnter={showTipSoon}
        onMouseLeave={hideTip}
        // hover 只给圆形细阴影，不做背景填充或缩放；原生 title 换成 portal tooltip,
        // 这里用 aria-label 保留可达性。
        className="inline-flex items-center justify-center p-1 -m-1 rounded-full cursor-pointer transition-shadow duration-150 hover:shadow-[0_0_0_1px_rgb(var(--color-border-hover))] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
        aria-label="点击更换项目 emoji"
        aria-haspopup="dialog"
        aria-expanded={pop.open}
      >
        {/* v5: 不再 scale, 静态 emoji */}
        {children}
      </button>
      {/* v6: 自定义 tooltip — picker 打开时不显示 (跟 trigger 状态互斥) */}
      {tip && !pop.open && mounted && createPortal(
        <div
          style={{
            position: "fixed",
            top: tip.top,
            left: tip.left,
            zIndex: 70,
            transform: tip.above ? "translate(-50%, -100%)" : "translate(-50%, 0)",
          }}
          className="tooltip-in pointer-events-none bg-bg-secondary border border-border rounded-md shadow-md px-2 py-1 text-[11px] text-fg-secondary whitespace-nowrap"
          role="tooltip"
        >
          更换项目 emoji
        </div>,
        document.body
      )}
      {pop.open && mounted && createPortal(
        <div
          ref={pop.popoverRef}
          style={{ position: "fixed", top: pos.top, left: pos.left, zIndex: pos.zIndex }}
          className="popover-in bg-bg-secondary border border-border rounded-lg shadow-xl p-2 w-[280px]"
          role="dialog"
          aria-label="选择项目 emoji"
          onClick={swallow}
          onMouseDown={swallow}
          onMouseDownCapture={swallow}
        >
          {/* 标题栏 */}
          <div className="mb-1.5 px-1.5">
            <span className="text-[11px] text-fg-muted">选个项目 emoji</span>
          </div>

          {/* emoji 网格 (10 列 × 5 行 = 50)
              v5 hover: 纯 bg 切换 (跟 app 整体 hover 语言一致)
              选中态: bg-accent/20 + ring-1 ring-accent/50 (常驻, 显眼但不抢戏) */}
          <div className="grid grid-cols-10 gap-0.5">
            {PROJECT_EMOJIS.map((emoji) => {
              const isCurrent = value === emoji;
              return (
                <button
                  key={emoji}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    selectEmoji(emoji);
                  }}
                  onMouseDown={(e) => e.stopPropagation()}
                  title={emoji}
                  className={`text-[18px] leading-none w-7 h-7 flex items-center justify-center rounded transition-colors duration-100 ${
                    isCurrent
                      ? "bg-accent/20 ring-1 ring-accent/50"
                      : "hover:bg-bg-tertiary"
                  }`}
                >
                  {emoji}
                </button>
              );
            })}
          </div>

          {/* 分隔 + 当前 hash 按钮 + 随机按钮 (v5: 纯 bg 切换, 跟 app 整体一致) */}
          <div className="border-t border-border/60 mt-2 pt-1.5 flex items-center justify-between gap-1 px-1">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                selectEmoji(hashEmoji);
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="text-[10.5px] text-fg-muted hover:text-fg hover:bg-bg-tertiary px-2 py-1 rounded-md transition-colors duration-150 flex items-center gap-1"
              title="点击恢复成自动 hash 算出的 emoji"
            >
              <span>当前 hash:</span>
              <span className="text-fg text-[14px]">{hashEmoji}</span>
              <span className="text-fg-muted text-[10px]" aria-hidden>
                ↩
              </span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                pickRandom();
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="text-[11px] text-fg-muted hover:text-fg hover:bg-bg-tertiary px-2 py-1 rounded-md transition-colors duration-150 flex items-center gap-1"
              title="从 50 个池子随机抽一个"
            >
              🎲 随机
            </button>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

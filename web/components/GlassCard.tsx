"use client";

import { forwardRef, type HTMLAttributes, type ReactNode } from "react";

/**
 * 2026-08-23 立: 玻璃拟态卡片基元 (cockpit v2 视觉重设计)
 *
 * 为什么需要这个组件, 而不是直接写 className:
 *   - backdrop-filter + 半透白底 + 内部高光 + 边框 = 4 个 class 必同时生效
 *   - 散落到每个组件 className 串里 = 容易漏一个, 玻璃感就破了
 *   - 抽基元后, 改一个地方 = 全站玻璃感统一
 *
 * 视觉 DNA (跟 globals.css 的 .glass utility 一致):
 *   - 背景: rgba(255,255,255, 0.04) 叠加在黑底
 *   - backdrop-filter: blur(24px) saturate(180%)
 *   - 边框: 1px rgba(255,255,255, 0.08)
 *   - 内部高光: inset 0 1px 0 0 rgba(255,255,255, 0.06)
 *   - 外部阴影: 0 8px 32px rgba(0,0,0, 0.4)
 *   - 圆角: 20px (默认) / 14px (sm) / 28px (lg)
 *
 * 用法:
 *   <GlassCard>默认内容</GlassCard>
 *   <GlassCard variant="strong" padding="lg">modal 内容</GlassCard>
 *   <GlassCard hover>Glow on hover</GlassCard>
 *   <GlassCard accent>霓虹绿发光边</GlassCard>
 */

type Variant = "default" | "strong";
type Padding = "none" | "sm" | "md" | "lg";
type Radius = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "glass", // 来自 globals.css utility
  strong: "glass-strong",
};

const PADDING_CLASSES: Record<Padding, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

const RADIUS_CLASSES: Record<Radius, string> = {
  sm: "rounded-glass-sm",
  md: "rounded-glass",
  lg: "rounded-glass-lg",
};

export interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  /** 玻璃强度: default (普通卡) / strong (modal/浮层, 更厚更不透明) */
  variant?: Variant;
  /** 内边距 */
  padding?: Padding;
  /** 圆角 */
  radius?: Radius;
  /** hover 时增强 (内部高光更亮, 边框更明显) */
  hover?: boolean;
  /** 霓虹绿发光环 (主按钮/active 状态卡用) */
  accent?: boolean;
  /** 子元素 */
  children?: ReactNode;
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(function GlassCard(
  {
    variant = "default",
    padding = "md",
    radius = "md",
    hover = false,
    accent = false,
    className = "",
    children,
    ...rest
  },
  ref,
) {
  const baseClass = VARIANT_CLASSES[variant];
  const paddingClass = PADDING_CLASSES[padding];
  const radiusClass = RADIUS_CLASSES[radius];

  // hover 状态: 用 group hover 让多个子元素可以独立响应
  const hoverClass = hover
    ? "transition-all duration-200 hover:glass-hover cursor-pointer"
    : "";

  const accentClass = accent ? "glow-accent-sm" : "";

  return (
    <div
      ref={ref}
      className={`${baseClass} ${radiusClass} ${paddingClass} ${hoverClass} ${accentClass} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
});

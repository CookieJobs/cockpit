"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

/**
 * 2026-08-23 立: 霓虹绿主按钮 (cockpit v2 视觉重设计)
 *
 * 用途: 主 CTA — 完成任务确认 / AI 发送 / AI 润色 等关键操作
 * 视觉: 霓虹绿底 (#00ff88) + 黑字 + box-shadow 发光环 + hover 增强
 *
 * 不用普通 button + className 串的原因:
 *   - glow box-shadow 的多层 alpha 写 4 行 className 太长
 *   - 后续如果改"按钮标准" (比如 accent 换成 emerald), 一个文件改完
 *
 * 变体:
 *   - primary: 霓虹绿底, 主操作
 *   - secondary: 玻璃底, 次要操作
 *   - ghost: 透明底, hover 出底色
 *   - danger: 红色, 不可逆操作 (删除项目等)
 */

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-accent text-bg hover:bg-accent-hover shadow-glow-accent-sm hover:shadow-glow-accent",
  secondary:
    "glass text-fg hover:glass-hover",
  ghost:
    "bg-transparent text-fg-secondary hover:text-fg hover:bg-glass/[0.06]",
  danger:
    "bg-danger text-bg hover:brightness-110 shadow-glow-danger",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "h-8 px-3 text-[12px] gap-1.5",
  md: "h-9 px-4 text-[13px] gap-2",
  lg: "h-11 px-5 text-[14px] gap-2",
};

export interface NeonButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children?: ReactNode;
}

export const NeonButton = forwardRef<HTMLButtonElement, NeonButtonProps>(function NeonButton(
  {
    variant = "primary",
    size = "md",
    loading = false,
    disabled,
    className = "",
    children,
    ...rest
  },
  ref,
) {
  const variantClass = VARIANT_CLASSES[variant];
  const sizeClass = SIZE_CLASSES[size];
  const isDisabled = disabled || loading;

  return (
    <button
      ref={ref}
      disabled={isDisabled}
      className={`
        inline-flex items-center justify-center
        font-medium rounded-glass-sm
        transition-all duration-150
        disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
        ${variantClass} ${sizeClass} ${className}
      `}
      {...rest}
    >
      {children}
    </button>
  );
});

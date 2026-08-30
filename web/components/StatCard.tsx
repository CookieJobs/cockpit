"use client";

import { type ReactNode } from "react";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";

/**
 * 2026-08-23 立: Stat 数字卡片 (cockpit v2 视觉重设计)
 *
 * 用途: 主页 4 个核心数字 (今日聚焦 / 今日已完成 / 逾期任务 / 已沉淀成就)
 * 视觉 DNA (参考图同款):
 *   - 玻璃底
 *   - 极大数字 (text-stat-xl, 56px) + 紧凑字距 + 粗字重
 *   - 下方小趋势指示: ↑/↓ 百分比 + 较上周/本月对比文案
 *   - 颜色: 数字继承父色, 趋势符号按方向 (绿/红/灰)
 *   - 顶部小图标 + label (e.g. 今日聚焦 + 圆点 + 颜色)
 *
 * 用法:
 *   <StatCard
 *     label="今日聚焦"
 *     value={focusCount}
 *     trend={{ direction: "up", value: 15, period: "本周" }}
 *     tone="accent"
 *   />
 */

type Direction = "up" | "down" | "flat";
type Tone = "accent" | "success" | "danger" | "warning" | "info" | "muted";

export interface StatCardProps {
  label: string;
  value: number | string;
  /** 趋势: up=涨 (通常好), down=跌, flat=持平 */
  trend?: {
    direction: Direction;
    value: number;
    period?: string;
  };
  /** 数字色调 — 默认主色, 也可按语义色 */
  tone?: Tone;
  /** 可选 icon (lucide, 16px) */
  icon?: ReactNode;
  /** 自定义 className */
  className?: string;
  /** 点击回调 (整卡可点) */
  onClick?: () => void;
}

const TONE_TEXT_CLASSES: Record<Tone, string> = {
  accent: "text-accent",
  success: "text-success",
  danger: "text-danger",
  warning: "text-warning",
  info: "text-info",
  muted: "text-fg",
};

const TONE_DOT_CLASSES: Record<Tone, string> = {
  accent: "bg-accent shadow-glow-accent-sm",
  success: "bg-success",
  danger: "bg-danger shadow-glow-danger",
  warning: "bg-warning",
  info: "bg-info",
  muted: "bg-fg-muted",
};

const TREND_COLOR_CLASSES: Record<Direction, string> = {
  up: "text-success",
  down: "text-danger",
  flat: "text-fg-muted",
};

const TREND_ICON: Record<Direction, typeof ArrowUp> = {
  up: ArrowUp,
  down: ArrowDown,
  flat: Minus,
};

export function StatCard({
  label,
  value,
  trend,
  tone = "muted",
  icon,
  className = "",
  onClick,
}: StatCardProps) {
  const toneText = TONE_TEXT_CLASSES[tone];
  const toneDot = TONE_DOT_CLASSES[tone];
  const interactive = Boolean(onClick);

  return (
    <div
      onClick={onClick}
      className={`
        glass rounded-glass p-4
        ${interactive ? "cursor-pointer transition-all duration-200 hover:glass-hover" : ""}
        ${className}
      `}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {/* 顶部: dot + label + 可选 icon */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full ${toneDot}`}
          aria-hidden
        />
        <span className="text-[11px] text-fg-secondary tracking-wide uppercase font-medium">
          {label}
        </span>
        {icon && <span className="ml-auto text-fg-muted">{icon}</span>}
      </div>

      {/* 中部: 大数字 */}
      <div className={`text-stat-lg ${toneText} tabular-nums`}>{value}</div>

      {/* 底部: 趋势 (可选) */}
      {trend && (
        <div className={`mt-1.5 flex items-center gap-1 text-[11px] ${TREND_COLOR_CLASSES[trend.direction]}`}>
          {(() => {
            const Icon = TREND_ICON[trend.direction];
            return <Icon size={11} strokeWidth={2.5} />;
          })()}
          <span className="font-medium tabular-nums">{trend.value}%</span>
          {trend.period && (
            <span className="text-fg-muted ml-0.5">{trend.period}</span>
          )}
        </div>
      )}
    </div>
  );
}

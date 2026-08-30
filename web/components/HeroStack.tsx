"use client";

import { useState, type ReactNode } from "react";
import { Sparkles } from "lucide-react";

/**
 * 2026-08-23 立 / 2026-08-26 改: 3D 卡片堆叠 — 主页 Hero 视觉
 *
 * 用途: 主页顶部中央, 3 张卡片 3D 透视堆叠, 顶层是当前 focus 任务
 * 视觉 DNA (对标参考图中央的卡片堆叠):
 *   - 3 张半透明卡片 (从 5 减到 3 — 5 张时 translateY 叠加超出容器,
 *     跟下面的 FocusSection 重叠, lesson #mainboard-hero-overflow)
 *   - perspective(1200px) + rotateX 透视
 *   - 底层卡片向后位移 + 缩小, 形成"叠"的感觉
 *   - 顶层卡片发光绿 accent 边 + Sparkles icon
 *
 * 修复 (2026-08-26):
 *   - depth 默认 5 → 3 (减少重叠, 适配 180px 容器)
 *   - translateY 14/层 → 6/层 (3 张 = 12px, 远小于容器)
 *   - 子元素用 SnapLayout padding, 不让内容溢出
 *   - hover 摊开: factor 1.5 保持
 */

export interface HeroStackProps {
  children: ReactNode;
  /** 堆叠层数, 默认 3 (v2 调小, 避免溢出) */
  depth?: number;
  className?: string;
}

export function HeroStack({ children, depth = 3, className = "" }: HeroStackProps) {
  const [hover, setHover] = useState(false);

  // 把 children 拍平取前 depth 个
  const items = Array.isArray(children) ? children : [children];
  const stack = items.slice(0, depth);

  // 堆叠参数: 底层 z 值越低, translateY 越大 (往后), scale 越小, opacity 越低
  // 2026-08-26 调小 translateY: 14 → 6, 3 张 = 12px 总位移, 远小于 180px 容器
  const offsets = Array.from({ length: depth }, (_, i) => ({
    z: -i * 20,
    y: i * 6,            // ↓ 6/层, 之前是 14
    scale: 1 - i * 0.05,
    opacity: 1 - i * 0.18,
    rotateX: hover ? -6 - i * 1.5 : -10 - i * 1.5,
  }));

  return (
    <div
      className={`perspective-card relative w-full ${className}`}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ minHeight: 160 }}
    >
      <div
        className="preserve-3d relative w-full"
        style={{ transformStyle: "preserve-3d" }}
      >
        {/* 倒序: z 最负的先渲染 (在底), 顶层最后渲染 */}
        {[...stack].reverse().map((child, reverseIdx) => {
          const i = stack.length - 1 - reverseIdx;
          const o = offsets[i];
          const isTop = i === 0;
          return (
            <div
              key={i}
              className={`
                absolute inset-0
                glass rounded-glass p-4
                ${isTop ? "ring-1 ring-accent/40 shadow-glow-accent-sm" : ""}
                transition-all duration-500 ease-out
              `}
              style={{
                transform: `translateZ(${o.z}px) translateY(${o.y}px) scale(${o.scale}) rotateX(${o.rotateX}deg)`,
                opacity: o.opacity,
                zIndex: depth - i,
              }}
            >
              {isTop && (
                <div className="absolute top-2.5 right-2.5 text-accent opacity-80">
                  <Sparkles size={13} />
                </div>
              )}
              {child}
            </div>
          );
        })}
      </div>
      {/* 占位: 给底层卡片提供布局高度, 因为 absolute 不占空间.
          180 → 160 (v2), 因为 translateY 总和变小, 容器可以更紧凑 */}
      <div className="invisible" style={{ height: 160 }} aria-hidden>
        placeholder
      </div>
    </div>
  );
}

/**
 * 单张 Hero 卡片的内容 (父组件传进来的 children 用这个包一下)
 */
export function HeroStackCard({
  title,
  subtitle,
  meta,
}: {
  title: string;
  subtitle?: string;
  meta?: string;
}) {
  return (
    <div className="h-full flex flex-col justify-between">
      <div>
        {subtitle && (
          <div className="text-[10px] uppercase tracking-[0.15em] text-fg-muted mb-1.5">
            {subtitle}
          </div>
        )}
        <div className="text-[14px] font-semibold text-fg leading-snug line-clamp-2">
          {title}
        </div>
      </div>
      {meta && (
        <div className="text-[10px] text-fg-muted mt-1.5 flex items-center gap-1.5">
          <span className="inline-block w-1 h-1 rounded-full bg-accent" />
          {meta}
        </div>
      )}
    </div>
  );
}

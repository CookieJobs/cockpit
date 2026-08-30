import type { Config } from "tailwindcss";

// 2026-08-23 改: cockpit v2 视觉重设计 — 深色玻璃拟态 + 3D 堆叠 + 霓虹绿。
// 保留 lesson #27 立的"函数形式" color 映射机制 (不能回归字符串,
//   否则 Tailwind 会把 var() 解析成字面值写死编译产物, 主题就死了)。
type RgbFn = (args: { opacityValue: number | undefined }) => string;

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  // 2026-07-23 立: 强制生成 P0/P1/P2/P3 badge 用的 4 个 alpha 变体, 跟 P1 行为对齐。
  // 2026-08-23 改: v2 加 accent (霓虹绿) 用的 0/30/50/70, 适配玻璃拟态叠加层
  safelist: [
    {
      pattern:
        /^(bg|border|text|ring)-(danger|warning|asset|info|success|fg|fg-secondary|fg-muted|accent|border|border-hover|bg-secondary|bg-tertiary|glass|glass-border)\/(0|5|8|10|15|20|30|35|40|50|70)$/,
    },
  ],
  theme: {
    extend: {
      colors: {
        // 2026-08-23 改: surface 层 — 纯黑 + 极深的渐变层次
        bg: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-bg) / ${opacityValue})`
              : "rgb(var(--color-bg))",
          secondary: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-bg-secondary) / ${opacityValue})`
              : "rgb(var(--color-bg-secondary))",
          tertiary: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-bg-tertiary) / ${opacityValue})`
              : "rgb(var(--color-bg-tertiary))",
        },
        border: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-border) / ${opacityValue})`
              : "rgb(var(--color-border))",
          hover: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-border-hover) / ${opacityValue})`
              : "rgb(var(--color-border-hover))",
        },
        // 2026-08-23 加: 玻璃拟态专用 — 半透明白色叠加, 用 alpha 控制强度
        glass: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-glass) / ${opacityValue})`
            : "rgb(var(--color-glass))",
        "glass-border": ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-glass-border) / ${opacityValue})`
            : "rgb(var(--color-glass-border))",
        fg: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-fg) / ${opacityValue})`
              : "rgb(var(--color-fg))",
          secondary: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-fg-secondary) / ${opacityValue})`
              : "rgb(var(--color-fg-secondary))",
          muted: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-fg-muted) / ${opacityValue})`
              : "rgb(var(--color-fg-muted))",
        },
        // 2026-08-23 改: accent 改霓虹绿 #00ff88 (从 indigo 4f46e5 改)
        accent: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-accent) / ${opacityValue})`
              : "rgb(var(--color-accent))",
          hover: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-accent-hover) / ${opacityValue})`
              : "rgb(var(--color-accent-hover))",
        },
        // 2026-08-23 改: 资产色保留金色 (跟霓虹绿区分)
        asset: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-asset) / ${opacityValue})`
              : "rgb(var(--color-asset))",
          hover: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-asset-hover) / ${opacityValue})`
              : "rgb(var(--color-asset-hover))",
        },
        // 2026-08-23 改: 语义色全部"亮一档" 适配纯黑底
        success: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-success) / ${opacityValue})`
            : "rgb(var(--color-success))",
        warning: {
          DEFAULT: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-warning) / ${opacityValue})`
              : "rgb(var(--color-warning))",
          hover: ({ opacityValue }: { opacityValue: number | undefined }) =>
            opacityValue !== undefined
              ? `rgb(var(--color-warning-hover) / ${opacityValue})`
              : "rgb(var(--color-warning-hover))",
        },
        danger: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-danger) / ${opacityValue})`
            : "rgb(var(--color-danger))",
        info: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-info) / ${opacityValue})`
            : "rgb(var(--color-info))",
      } as any,
      // 2026-08-23 加: 玻璃拟态 backdrop blur 预设
      backdropBlur: {
        glass: "24px",
        "glass-lg": "32px",
        "glass-sm": "12px",
      },
      // 2026-08-23 加: 玻璃卡片 + 发光阴影
      boxShadow: {
        // 标准玻璃卡: 内部高光 + 外部深阴影
        glass:
          "inset 0 1px 0 0 rgb(255 255 255 / 0.06), 0 8px 32px rgb(0 0 0 / 0.4)",
        // 玻璃卡 hover: 内部高光更亮
        "glass-hover":
          "inset 0 1px 0 0 rgb(255 255 255 / 0.10), 0 12px 40px rgb(0 0 0 / 0.5)",
        // 霓虹绿发光 (主按钮 / active 状态)
        "glow-accent":
          "0 0 0 1px rgb(var(--color-accent) / 0.5), 0 0 16px rgb(var(--color-accent) / 0.4), 0 0 32px rgb(var(--color-accent) / 0.2)",
        "glow-accent-sm":
          "0 0 8px rgb(var(--color-accent) / 0.3), 0 0 16px rgb(var(--color-accent) / 0.15)",
        "glow-accent-lg":
          "0 0 24px rgb(var(--color-accent) / 0.5), 0 0 48px rgb(var(--color-accent) / 0.3), 0 0 80px rgb(var(--color-accent) / 0.15)",
        // 红色发光 (overdue 强调)
        "glow-danger":
          "0 0 12px rgb(var(--color-danger) / 0.4), 0 0 24px rgb(var(--color-danger) / 0.2)",
        // 卡片悬浮 (通用)
        "card-lift":
          "0 4px 16px rgb(0 0 0 / 0.3), 0 1px 0 rgb(255 255 255 / 0.04) inset",
        "card-lift-hover":
          "0 8px 32px rgb(0 0 0 / 0.5), 0 1px 0 rgb(255 255 255 / 0.08) inset",
      },
      // 2026-08-23 加: 3D 透视 — 卡片堆叠用
      perspective: {
        card: "1200px",
        "card-tight": "800px",
      },
      // 2026-08-23 加: 玻璃大圆角
      borderRadius: {
        glass: "20px",
        "glass-sm": "14px",
        "glass-lg": "28px",
      },
      // 2026-08-23 加: 数字 tabular-nums 已经在用, 加大字号 preset
      fontSize: {
        "stat-xl": ["3.5rem", { lineHeight: "1", letterSpacing: "-0.04em", fontWeight: "700" }],
        "stat-lg": ["2.5rem", { lineHeight: "1", letterSpacing: "-0.03em", fontWeight: "700" }],
        "stat-md": ["1.75rem", { lineHeight: "1.1", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: ["SF Mono", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      // 2026-08-23 加: 3D 关键帧 — 卡片堆叠入场
      keyframes: {
        "stack-in": {
          "0%": { opacity: "0", transform: "translateY(40px) rotateX(-20deg)" },
          "100%": { opacity: "1", transform: "translateY(0) rotateX(0)" },
        },
        "glow-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
      },
      animation: {
        "stack-in": "stack-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;

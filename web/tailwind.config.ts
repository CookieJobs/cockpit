import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  // 2026-07-23 加: Tailwind 3.4 的 alpha 变体 (`bg-info/15` 等) 是 JIT 按需生成 ——
  //   只扫到源码里**实际写过**的 class 才会生成。自定义色 danger/warning/info/success
  //   之前在 PRIORITY_BADGE_STYLES 字符串字面量里写过 `/15` `/30`, 但 Tailwind 扫字符串
  //   字面量里的 class 名不可靠 (有时扫到有时扫不到), 结果 P0/P2/P3 的 bg/border 透明
  //   变体没生成, badge 渲染成"白底白框" (其实是没生成 class, fallback 到默认色)。
  //   safelist 强制生成 P0/P1/P2/P3 badge 用的 4 个 alpha 变体, 跟 P1 行为对齐。
  safelist: [
    {
      pattern:
        /^(bg|border)-(danger|warning|info|success)\/(10|15|20|30|40|50)$/,
    },
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0a0a0a",
          secondary: "#141414",
          tertiary: "#1e1e1e",
        },
        border: {
          DEFAULT: "#2a2a2a",
          hover: "#3a3a3a",
        },
        fg: {
          DEFAULT: "#e5e5e5",
          secondary: "#a0a0a0",
          muted: "#666666",
        },
        accent: {
          DEFAULT: "#fbbf24",
          hover: "#f59e0b",
        },
        // 2026-07-23 改 rgb() 格式: 跟字符串 hex 比, Tailwind 对 rgb() 字符串色
        //   的 alpha 变体生成更稳定 (作为额外保险, safelist 仍保留)。
        success: "rgb(34 197 94)",
        warning: "rgb(245 158 11)",
        danger: "rgb(239 68 68)",
        // 2026-07-23 立: 给 P2 (普通优先级) 用冷色, 跟 P0/P1 暖色 (红/橙) 拉开对比
        //   红 0° → 橙 30° → 蓝 220°: 跨越色环 ~200°, 一眼区分
        info: "rgb(59 130 246)",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "sans-serif"],
        mono: ["SF Mono", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;

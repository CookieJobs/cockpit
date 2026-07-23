import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
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
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
        // 2026-07-23 立: 给 P2 (普通优先级) 用冷色, 跟 P0/P1 暖色 (红/橙) 拉开对比
        //   红 0° → 橙 30° → 蓝 220°: 跨越色环 ~200°, 一眼区分
        info: "#3b82f6",
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

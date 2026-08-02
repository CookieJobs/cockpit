import type { Config } from "tailwindcss";

// 2026-08-02 修: Tailwind 3 官方文档说 colors 支持函数形式 (运行时) —
//   ({ opacityValue }: { opacityValue: number | undefined }) => opacityValue ? `rgb(...)` : `rgb(...)` —
//   但官方 .d.ts 类型 Config.colors 仍是 string | RecursiveKeyValuePair<string, string>,
//   没暴露函数签名。直接 any 绕过, runtime OK。
// 替代方案: 把整个 config 标 any — 但会丢其他字段的类型保护 (比如 darkMode: "class")。
// 选局部 any, 影响面最小。
type RgbFn = (args: { opacityValue: number | undefined }) => string;

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  // 2026-08-01 立: 主题切换 (light/dark) 需要 class 策略。配合 globals.css 里
  //   :root (light) + .dark (dark) 两套 CSS 变量, 切 html class 即可换主题。
  darkMode: "class",
  // 2026-07-23 加: Tailwind 3.4 的 alpha 变体 (`bg-info/15` 等) 是 JIT 按需生成 ——
  //   只扫到源码里**实际写过**的 class 才会生成。自定义色 danger/warning/info/success
  //   之前在 PRIORITY_BADGE_STYLES 字符串字面量里写过 `/15` `/30`, 但 Tailwind 扫字符串
  //   字面量里的 class 名不可靠 (有时扫到有时扫不到), 结果 P0/P2/P3 的 bg/border 透明
  //   变体没生成, badge 渲染成"白底白框" (其实是没生成 class, fallback 到默认色)。
  //   safelist 强制生成 P0/P1/P2/P3 badge 用的 4 个 alpha 变体, 跟 P1 行为对齐。
  safelist: [
    {
      pattern:
        /^(bg|border)-(danger|warning|info|success|fg|fg-secondary|fg-muted|accent|border|border-hover|bg-secondary|bg-tertiary)\/(10|15|20|30|40|50)$/,
    },
  ],
  theme: {
    extend: {
      // 2026-08-02: 颜色必须用函数形式, Tailwind 不会解析 var() ——
      //   但官方类型不允许函数 (Config.colors 类型缺函数签名),
      //   整个 colors 块用 `as any` 绕过 — runtime OK。
      colors: {
        // 2026-08-02 修: 字符串 "rgb(var(--color-X) / <alpha-value>)" 写法被 Tailwind 3
        //   解析, 解析时用当前 css 变量值 (dark mode 的 10 10 10) 当 fallback 写死
        //   到编译产物。结果: 切 light 模式 html class 也好, 页面永远是 dark (硬
        //   编码的 dark 值), 主题切换看不到任何变化。修法: 用**函数形式**告诉
        //   Tailwind "这值运行时由 css 变量决定, 别解析" — Tailwind 文档明确: 函
        //   数形式不会被颜色解析器碰, 直接原样输出 var()。
        //
        //   函数形态: ({ opacityValue }: { opacityValue: number | undefined }) => opacityValue !== undefined
        //     ? `rgb(var(--color-X) / ${opacityValue})`
        //     : `rgb(var(--color-X))`
        //   - opacityValue undefined: 写 `rgb(var(--color-X))` (无 alpha 变体)
        //   - opacityValue = 0.5: 写 `rgb(var(--color-X) / 0.5)` (alpha 变体替换)
        //
        // 验证: 修完重启 dev, 编译产物应保留 `rgb(var(--color-X))` 而非 `rgb(10 10 10)`。
        // lesson 立: 架构层字符串能 grep, 编译产物要真看 — 不变量测试只锁"代码这么写",
        // 锁不住"Tailwind 把我的字符串解析成啥" (#27 补, 跟 #2/#15/#17 同源)。
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
        // success/warning/danger/info 同样用函数形式
        success: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-success) / ${opacityValue})`
            : "rgb(var(--color-success))",
        warning: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-warning) / ${opacityValue})`
            : "rgb(var(--color-warning))",
        danger: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-danger) / ${opacityValue})`
            : "rgb(var(--color-danger))",
        // 2026-07-23 立: 给 P2 (普通优先级) 用冷色, 跟 P0/P1 暖色 (红/橙) 拉开对比
        info: ({ opacityValue }: { opacityValue: number | undefined }) =>
          opacityValue !== undefined
            ? `rgb(var(--color-info) / ${opacityValue})`
            : "rgb(var(--color-info))",
      } as any,
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "sans-serif"],
        mono: ["SF Mono", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;

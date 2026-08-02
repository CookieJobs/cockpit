---
date: 2026-08-01
slug: theme-toggle
title: 主题切换 (light / dark) v1
status: 现行
supersedes: —
related_lessons: #17
---

## Changelog: 2026-08-01 主题切换 (light / dark) v1

用户原话: "现在产品的主题色是黑色, 我想增加一个黑夜和白天模式切换的功能"。

### 调查 + 根因

旧架构 dark only: `tailwind.config.ts` 里 colors 全硬编码 (bg='#0a0a0a' / fg='#e5e5e5' / accent='#fbbf24'), `globals.css` 里 `.markdown *` 系列 11 条样式也全部 hardcode dark hex (pre / blockquote / th / a / strong / code / hr / checkbox / scrollbar / body bg / cursor-blink)。

直接加 `dark:` 前缀的方案不可行 — 302 处用了 `bg-bg-*` / `text-fg-*` / `border-border*`, 每个组件写两套等于全项目返工。

唯一干净路径: **CSS variables 双套 + `darkMode: 'class'`** — 把硬编码 token 全改成 `rgb(var(--color-X) / <alpha-value>)` 引用, html class 切 light/dark 即全页换。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **`tailwind.config.ts` 加 `darkMode: "class"`** | 同文件 | 配合 globals.css 双套变量, 切 html class 即可换主题 |
| 2 | **所有 colors token 改 CSS variables 引用** | `tailwind.config.ts` | 存 "R G B" 三元组, `rgb(var(--color-X) / <alpha-value>)` 引用 — Tailwind 自动展开 alpha 变体 (`bg-danger/15` → `rgb(239 68 68 / 0.15)`), light/dark 双套都正确 |
| 3 | **`globals.css` 重构双套变量** | 同文件 | `:root` (light 默认) + `.dark` (覆盖), 各 14 个 `--color-X` (bg×3 / border×2 / fg×3 / accent×2 / success/warning/danger/info) + `color-scheme` 决定原生组件 (scrollbar / 表单) |
| 4 | **`.markdown *` 11 条样式全改 var()** | `globals.css` | pre / blockquote / th / a / hr / strong / code / checkbox / scrollbar / body bg / cursor-blink — 漏一处切 light 时该块不变, 视觉撕裂 |
| 5 | **早期同步脚本 (防 FOUC)** | `web/app/layout.tsx` | `<head>` 顶部 `dangerouslySetInnerHTML` 注入 inline JS, **同步执行**, 读 `localStorage['cockpit_theme']` 切 `.dark`/`.light` class + `data-theme` 属性 |
| 6 | **`<html suppressHydrationWarning>`** | `web/app/layout.tsx` | server 渲染时无 class, client 早期脚本立即加 class — 之间的"不一致"是设计如此, 不该让 React 报 warning |
| 7 | **viewport 去掉硬编码 `themeColor: "#0a0a0a"`** | `web/app/layout.tsx` | Next.js viewport export 是静态, 不能跟主题切换 — 改靠 CSS `color-scheme` 决定原生组件颜色 |
| 8 | **拆 `lib/theme-core.ts` (纯函数) + `lib/theme.ts` (hook)** | `web/lib/` | 纯函数无 React 依赖, mjs 端到端能 import 跑真实验证; hook 用 `useSyncExternalStore` 订阅 + `storage` 事件多 tab 同步 |
| 9 | **`useTheme()` hook** | `web/lib/theme.ts` | `useSyncExternalStore(subscribe, snapshot, serverSnapshot)`, setTheme + toggle 便捷方法 |
| 10 | **`ThemeToggle` 组件** | `web/components/ThemeToggle.tsx` (新) | lucide Sun/Moon (跟整站 icon 语言一致), 16x16 button, hover bg-bg-tertiary (跟 Settings 同款风格), `data-testid` + `data-theme-state` 便于 e2e |
| 11 | **MainBoard 顶栏挂 `<ThemeToggle />`** | `web/components/MainBoard.tsx` | Settings 链接旁边, 视觉权重一致 |
| 12 | **不变量测试 17 条** | `app/tests/test_theme_toggle_invariants.py` (新) | 锁: layout.tsx 无硬编码 className="dark" / 早期脚本有 / suppressHydrationWarning / viewport 无 themeColor / tailwind darkMode='class' / colors 用 var() / safelist 保留 / globals.css 双套变量各 ≥12 个 / 无硬编码 dark hex (11 个 forbidden) / body 用 var() / ThemeToggle data-testid+useTheme+icon / MainBoard 挂载 / lib/theme-core 工具齐 / lib/theme re-export+useSyncExternalStore+storage 监听 / **端到端 mjs 跑过 33 用例** |
| 13 | **端到端 mjs 33 用例** | `web/scripts/test-theme-core.mjs` (新) | node 22 `--experimental-strip-types` 真跑, 手写 mock DOM + localStorage, 覆盖: roundtrip / 容错 (rainbow/空串/抛错) / applyTheme 切 class / 互斥 / getCurrentTheme 读 DOM / toggleTheme 翻转 / subscribe+bump / SSR 安全 / 完整循环 |
| 14 | **lesson #17 立** | `docs/lessons/05-theme-system.md` (新) + `docs/lessons/README.md` 索引 | 主题系统架构教训: CSS variables 双套 + 早期同步脚本 + 端到端 mjs 同源教训 |

### 设计决定记录

**A. CSS variables 双套 vs `dark:` 前缀 vs runtime js**

- `dark:` 前缀: 302 处全改, 改造成本爆炸, 跟 `bg-bg-secondary` 现有用法对不上
- runtime js 改 style: 性能差 + 改一处忘一处
- 选 CSS variables: 一次改 token 层, 组件零改, Tailwind 自动展开 alpha 变体
- lesson: **架构层的 token 化 = 一次到位, 优于逐组件 hack**

**B. 颜色存 "R G B" 三元组 + `rgb(var() / <alpha-value>)`**

- 存 `var(--color-fg): #e5e5e5` 形式: alpha 变体 (`bg-fg/15`) 失效, Tailwind 不知道怎么拆
- 存 `var(--color-fg): 229 229 229` 形式 + `fg: "rgb(var(--color-fg) / <alpha-value>)"`: Tailwind 自动展开 `bg-fg/15` → `rgb(229 229 229 / 0.15)`, alpha 变体在 light/dark 双主题下都正确
- lesson: **CSS variables 用三元组 + alpha-value 模板, 是 Tailwind 3 唯一干净支持 alpha 变体的方式**

**C. 早期同步脚本在 `<head>` 顶部, 不在 body 末尾**

- 早期脚本必须**在 React 渲染前**执行 — 否则 React 渲染时 html 还没 class, 渲染出 "默认色", 然后脚本改 class, 用户看到闪一下
- 放 `<head>` 顶部 + 同步 (无 defer/async): 浏览器解析到这里立即跑, 早于 React mount
- 副作用: server render html 时无 class, client 早期脚本改 class → React hydration warning, 必须 `suppressHydrationWarning`
- lesson: **防 FOUC 不是优化, 是核心需求 — 早期同步脚本缺一个字节都会闪**

**D. 拆 `theme-core.ts` (纯) + `theme.ts` (hook)**

- 纯函数 (getStoredTheme / setStoredTheme / applyTheme / getCurrentTheme / toggleTheme / subscribe / bump) 无 React 依赖, mjs 端到端能 import 跑真实验证
- React hook (useTheme) 用 `useSyncExternalStore` 订阅, 必须在 Next.js 环境跑
- 拆开的好处: lesson #2/#15 同源教训 — **单测过 ≠ 真实数据过**, mjs 端到端捕获了 4 类 bug (mock 错位、断言数错、容错路径漏、catch 语法)
- 选 `useSyncExternalStore` 而不是 useState + useEffect: 主题是**外部状态** (localStorage + DOM), useState 不触发跨组件同步, useEffect 在 SSR 阶段多一次 render

**E. 默认 dark 而不是 light 或 system**

- 默认 dark: 跟产品原观感一致, 渐进增强, 老用户不打扰
- 默认 light: 跟 web 主流约定, 但打破老用户预期
- 默认 system (prefers-color-scheme): 简化产品, 但用户想"我要白天"的需求被系统绑架
- 选 dark: lesson 同源 — **默认值是行为信号**, "新用户看到产品历史样貌" 表达"我们尊重存量"

**F. 不存 'system' 模式**

- 三态 (light/dark/system) 看起来更灵活, 实际 UX 上多一档选择 = 决策疲劳
- 用户明确表达 "我想要白天" 比"系统说啥我信啥" 更可控
- 简化 toggle 按钮为一键翻转, 不引入 dropdown
- lesson: **"少一档选择" 比"多一档灵活" 更尊重用户** — 跟 StatusMenu 末尾 blocked/draft toggle 同源

**G. 多 tab 同步用 `storage` 事件, 不用 BroadcastChannel**

- `storage` 事件: 浏览器原生支持, 跨 tab 同步, 零依赖
- `BroadcastChannel`: 需要 polyfill + 显式管理 channel, 跟 localStorage 不直接对接
- 选 storage 事件: 简单, 跟 localStorage 是天然搭档, 旧浏览器兼容好

**H. mjs 端到端 33 用例 vs 纯 pytest**

- pytest 静态不变量锁"代码这么写了", 但不能锁"运行时这么跑"
- mjs 端到端真跑, 捕获: mock localStorage 没装到 `window.localStorage` (我第一次跑全失败才发现); `bump 4 次累计 +4` 断言数错; `catch {` Node 22 strip-types 模式下语法错; `applyTheme` 跟 `setStoredTheme` 调用顺序问题
- lesson: **架构层字符串能 grep, 行为层得真跑** — 跟 lesson #2/#15 同源

**I. 端到端 mjs 不依赖 jsdom / vitest / playwright**

- 装 vitest 改造 3 个文件 (package.json / vitest.config / 测试写法), 对这个项目太重
- Node 22.6+ 原生支持 `--experimental-strip-types`, 直接 `import '../lib/theme-core.ts'`, 0 额外依赖
- 手写 mock DOM (ClassList + setAttribute + getAttribute) ~30 行, 比装 jsdom (整个库) 简单
- 跑法: `node --experimental-strip-types web/scripts/test-theme-core.mjs` — 接入 pytest 用 `subprocess.run`, 端到端测试 0 外部依赖

### 颜色梯度对照

| Token | Light hex | Dark hex | 色环 hue | 备注 |
|---|---|---|---|---|
| bg | #ffffff | #0a0a0a | n/a | 主背景 |
| bg-secondary | #f5f5f5 | #141414 | n/a | 卡片/次级容器 |
| bg-tertiary | #e8e8e8 | #1e1e1e | n/a | 三级容器/输入框 |
| border | #d4d4d4 | #2a2a2a | n/a | 边框/分割线 |
| border-hover | #a3a3a3 | #3a3a3a | n/a | hover 边框 |
| fg | #0a0a0a | #e5e5e5 | n/a | 主文字 |
| fg-secondary | #525252 | #a0a0a0 | n/a | 次级文字 |
| fg-muted | #737373 | #666666 | n/a | 弱化文字/占位符 |
| accent | #d97706 (amber-600) | #fbbf24 (amber-400) | 30° | **light 用 600, dark 用 400** — 白底上 amber-400 对比度 1.7:1 不够, amber-600 是 4.5:1+ 满足 WCAG AA |
| accent-hover | #b45309 (amber-700) | #f59e0b (amber-500) | 30° | hover 加深一档 |
| success | #16a34a (green-600) | #22c55e (green-500) | 142° | light 用 600, dark 用 500 |
| warning | #d97706 (amber-600) | #f59e0b (amber-500) | 30° | 同 accent 逻辑 |
| danger | #dc2626 (red-600) | #ef4444 (red-500) | 0° | 同上 |
| info | #2563eb (blue-600) | #3b82f6 (blue-500) | 220° | 同上 |

### 字段表 (主题切换后)

| 系统 | 之前 (dark only) | 之后 (light/dark) |
|---|---|---|
| html class | 硬编码 `className="dark"` | 早期脚本决定 (默认 `dark`, localStorage 优先) |
| html themeColor | 硬编码 `#0a0a0a` | 删, 改靠 CSS `color-scheme` |
| 颜色 token | `tailwind.config.ts` 硬编码 hex | `rgb(var(--color-X) / <alpha-value>)` 引用 |
| markdown 样式 | 11 条硬编码 dark hex | 全部 `var(--color-X)` 引用 |
| 主题切换入口 | 无 | 顶栏 Sun/Moon IconButton, localStorage 持久化, 多 tab 同步 |
| 主题默认值 | n/a (只有 dark) | dark (产品原观感) |
| 主题持久化 | n/a | `localStorage['cockpit_theme']` |

### 验证

- `npx tsc --noEmit` — 0 错误
- 后端测试套件 — **294 passed, 1 skipped** (从 277 → 294, +17 主题切换不变量测试, 0 回归)
- 端到端 mjs — **33 passed, 0 failed** (Node 22 真跑 `lib/theme-core.ts` 真实函数)
- dev server (port 3000) curl 验证 — HTML 含早期脚本 + `data-testid="theme-toggle"` + `title="切换到白天模式"` (默认 dark, 按钮提示切到 light)

**回归**: 277 → **294** tests pass (+17 主题切换静态不变量 + 端到端调 mjs 33 用例同步). `tsc --noEmit` 0 错误. 改动 1 新后端测试 + 1 新前端测试脚本 + 1 新前端组件 + 1 改 lib 拆 2 文件 + 1 改 globals.css 完全重写 + 1 改 tailwind.config.ts + 1 改 layout.tsx + 1 改 MainBoard.tsx + 1 新 lesson 文件, 净 +约 1100 行 (含 700 行测试), 用户视觉上多一个 Sun/Moon 按钮 (顶栏 Settings 旁), 点了切到白底黑字, 再点回黑底白字 — 跨刷新保留, 多 tab 同步.


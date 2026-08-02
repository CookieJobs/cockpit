---
date: 2026-07-22
slug: markdown-upgrade
title: 消息泡 Markdown 升级 (手写 v1.0 → react-markdown + GFM + 高亮)
status: 现行
supersedes: —
related_lessons: —
---

## Changelog: 2026-07-22 消息泡 Markdown 升级 (手写 v1.0 → react-markdown + GFM + 高亮)

用户反馈: 右侧对话框消息泡的文本没解析 Markdown, Agent 拆任务的 "1. **xxx**" 退化成裸文本段落, 视觉很丑。

### 调查发现 (跟用户预期不同)

不是"没解析", 是**手写极简解析器太简陋** — `web/components/Markdown.tsx` v1.0 只支持 # 标题 / 无序列表 / `**bold**` / `` `code` ``。源码注释里其实埋了伏笔:

> // 简单 Markdown 解析 (v1.0 轻量级, LLM 接入后可替换为 react-markdown)

**不支持的 (用户痛点)**:
- ❌ 有序列表 `1. 2. 3.` — Agent 拆任务必用
- ❌ 任务清单 `- [x] / - [ ]` — GFM
- ❌ 引用块 `>` — 没左侧色条
- ❌ 多行代码块 ` ```tsx ` — 全糊成一坨
- ❌ 链接 `[text](url)` — 不识别
- ❌ 表格 `| --- |`
- ❌ 分割线 `---`

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **`web/components/Markdown.tsx` 完全重写 v1.0 → v2.0** | 同文件 | 从 100 行手写解析器换成 `<ReactMarkdown>` 包装, 配置 `remarkPlugins=[remarkGfm]` + `rehypePlugins=[rehypeHighlight]`, 链接默认 `target="_blank" rel="noopener noreferrer"`, 顶部 `import "highlight.js/styles/github-dark.css"` |
| 2 | **`web/components/ChatWindow.tsx` 改用 `MarkdownView` 组件** | 行 5 (import) + 退化路径 + EventsView | 删除 `renderMarkdown` 函数引用, EventsView 流式期也跑 markdown (用户拍板) |
| 3 | **`web/app/globals.css` 补 markdown prose 样式** | 新增 pre / blockquote / table / a / hr / task list / h4-h6 样式 | 沿用 `.markdown` className, 复用现有颜色 token (accent / border / bg-secondary 等) |
| 4 | **`web/package.json` 装 4 个依赖** | `react-markdown@9.1.0` + `remark-gfm@4.0.1` + `rehype-highlight@7.0.2` + `highlight.js@11.11.1` | 共 +105 包, 增量 build size 约 6KB (First Load JS 108→108KB, react-markdown chunk 拆出去了) |
| 5 | **不变量测试 6 条新增** | `app/tests/test_markdown_render_invariants.py` (新文件) | 锁住 react-markdown + remark-gfm + rehype-highlight 配置; 锁住流式期也走 MarkdownView; 锁住不能回退到 `whitespace-pre-wrap` + `{e.content}` 纯文本策略 |
| 6 | **顺手修 priority badge 测试位置 bug** | `app/tests/test_complete_path_invariants.py` | `test_priority_badge_styles_4_levels` 之前扫 `MainBoard.tsx` 找 `PRIORITY_BADGE_STYLES`, 但实际常量在 `lib/api.ts` 共享给 FocusItem/TaskRow。改扫 `lib/api.ts` |

### 设计决定记录

- **react-markdown + GFM + 高亮, 不扩展手写解析器**:
  - 注释里 2026-07-17 就埋了"可替换为 react-markdown" 的伏笔
  - 手写解析器本质是亡羊补牢, 永远追 LLM 实际用法 (3 个新语法后又会有 5 个)
  - 业界标准, 社区活跃, 一次到位覆盖 GFM 全部特性

- **流式期也跑 markdown, 接受小闪烁 (用户拍板)**:
  - v1.0 策略: 流式期纯文本 + 闪烁光标 → 结束后跑 markdown (避免增量解析闪烁)
  - v2.0 策略: 流式期也跑 markdown → 视觉连贯, 代价是增量解析时 block 结构变化
    (比如 "1. " 变 `<ol>`, 或代码块开始) 会有小 layout shift
  - 增量解析成本: react-markdown 处理 1KB markdown 约 30-50ms, 流式期每段 delta
    进来重解析一次, 用户感知不到
  - **保持光标**: 流式期最后 text 段渲染完 MarkdownView 后, 追加一个
    `<span className="cursor-blink">▍</span>` 元素 (在 markdown 容器外,
    inline 跟在最后 block 元素后, block 结束后会换行)

- **`MarkdownView` 是 "use client" 组件**:
  - react-markdown 9 用了 hooks (useState), 必须 client 化
  - 跟 ChatWindow 一样是 client, 不传染
  - Next.js 静态导出 (`output: 'export'`) 时仍能 SSR 渲染 (dev server 测试过,
    build 也过)

- **不依赖 `@tailwindcss/typography` plugin**:
  - 加 plugin 改 3 个文件 (tailwind.config / package.json / globals.css),
    项目用 5 个颜色 token (accent / border / bg-*), prose 默认 token 不一定合适
  - 手写 11 条 .markdown 样式 (~80 行 CSS) 反而更可控, 跟现有 dark theme 完美融合

- **代码块高亮选 github-dark**:
  - highlight.js 163 个内置主题, github-dark 跟 Cockpit 暗色 + 黄色 accent 风格契合
  - 行内 `<code>` 不在 `<pre>` 内, hljs 主题不会染它 (跟现有 .markdown code 背景
    协调)

- **删了手写 `renderMarkdown` 函数, 不保留 deprecated 导出**:
  - ChatWindow 是唯一调用方, 改 MarkdownView 组件 1 个文件 + 1 个调用点,
    没必要留 deprecated 壳子
  - lesson: 100% 替换 vs 渐进式迁移, 看具体场景 — 这里调用方单一, 一次到位
    比保留 deprecated API 干净

### 字段表 (markdown 升级后的支持范围)

| markdown 元素 | v1.0 (手写) | v2.0 (react-markdown) |
|---|---|---|
| `# ## ### #### ##### ######` 标题 | ✅ | ✅ |
| `-` `*` 无序列表 | ✅ | ✅ |
| `1. 2. 3.` 有序列表 | ❌ → 段落 | ✅ |
| `- [ ]` `- [x]` 任务清单 (GFM) | ❌ | ✅ |
| `> 引用` 块 | ❌ → 段落 | ✅ 左侧色条 |
| ` ```tsx ` 多行代码块 | ❌ → 段落 | ✅ 语法高亮 |
| ` `code` ` 行内代码 | ✅ | ✅ |
| `**bold**` 加粗 | ✅ | ✅ accent 色 |
| `*italic*` 斜体 | ❌ | ✅ |
| `[text](url)` 链接 | ❌ | ✅ 新窗口 |
| `\|` `---` 表格 | ❌ → 多行段落 | ✅ 边框 + 表头 |
| `---` 分割线 | ❌ | ✅ |
| `~~strikethrough~~` (GFM) | ❌ | ✅ |

**回归**: 164 → **170** tests pass (+6 新增 markdown 不变量; 顺手修了 1 个 priority badge 测试位置 bug; 其他 priority 套件 0 变化). `tsc --noEmit` 0 错误. `npm run build` 10/10 静态页导出通过, 增量 +6KB First Load JS (chunks 拆出去了).


# 05 — 主题系统 (light / dark) 主题 Lessons

> 2026-08-01 立 light/dark 主题切换时立的教训。这一类坑是**架构层**的, 跟
> #1 前端 UX bug / #3 后端工具类 都不同 — 是设计模式 (CSS variables) 选错,
> 会导致全项目颜色 token 全部要改, 或者切主题时闪一下。

## #17. 主题切换架构 (修于 2026-08-01)

### 症状
用户报: "现在产品的主题色是黑色, 我想增加一个黑夜和白天模式切换的功能"。

如果直接干 (在每个组件加 `dark:` 前缀), 会有 3 个典型坑:
1. **切主题时整页闪一下** (FOUC) — server 渲染时无 class, client mount 后才切, 中间几百毫秒的"白闪" 用户感知明显
2. **颜色 token 没重构, 切了也没用** — 旧代码 `bg-[#0a0a0a]` / `bg-fg-muted` 用了硬编码, 切 class 后**只有**走 CSS variables 的部分变了, 散落的硬编码色不变, 视觉撕裂
3. **markdown 样式漏改** — `.markdown` 系列 11 条样式 (代码块/链接/引用/表格/hr) 都硬编码了 dark hex, 不重构的话 chat 区域切 light 模式后还有一块是黑的

### 根因 (三重)
1. **没早做主题系统** — 项目上线时就 dark only, 颜色全 hardcode 进 `tailwind.config.ts` (静态 `colors: { bg: '#0a0a0a' }`), 没预留 CSS variables 通道
2. **没考虑 SSR/CSR 边界** — server render 时 html 上没 class, client mount 后早期脚本才加 class, 中间窗口 React hydration warning + 用户视觉感知闪
3. **没全栈扫颜色硬编码** — 改了 `tailwind.config.ts` 不算完, `globals.css` 里 `.markdown *` 系列还有 11 条 hardcode hex (blockcode / pre / th / blockquote / strong / code / a / hr / accent color), 一行行手改

### 教训 (5 条)

1. **CSS variables 双套 + `darkMode: 'class'` 是唯一干净的方案**
   - 其他方案: (a) `dark:` 前缀 + 每个组件写两套 — 302 处全改, 改造成本爆炸; (b) 运行时 js 改 style.background — 性能差, 改一处忘一处; (c) media query `prefers-color-scheme` — 不能主动切, 用户需求 "我想要白天" 满足不了
   - 选定: `tailwind.config.ts` 里 `colors.X = "rgb(var(--color-X) / <alpha-value>)"`, `globals.css` 里 `:root` (light) + `.dark` (dark) 两套变量, Tailwind 自动展开 alpha 变体 (`bg-danger/15` → `rgb(239 68 68 / 0.15)`), 切 html class 即可全页换
   - **关键 trick**: 颜色存 "R G B" 三元组 (无 `rgb()` 包装), 引用时才 `rgb(var() / <alpha-value>)`, alpha 变体才正确

2. **早期同步脚本是防 FOUC 的核心, 不是优化**
   - 放在 `<head>` 顶部, `dangerouslySetInnerHTML` 注入 inline JS, **同步执行** (不能 defer/async)
   - 读 `localStorage['cockpit_theme']`, 切 `.dark` / `.light` class + `data-theme` 属性
   - React `<html>` 标签必须 `suppressHydrationWarning` — server render 时 html 无 class, client 早期脚本立即加 class, 这之间的"不一致" 是设计如此, 不该让 React 报 warning
   - 跟 lesson #16 "next build 污染 dev server" 同源: 都是 SSR/CSR 边界问题, 必须早期同步处理

3. **React 18+ 用 `useSyncExternalStore` 订阅主题, 不用 useState + useEffect**
   - 主题 = 外部状态 (localStorage + DOM), 适合 `useSyncExternalStore` 订阅, 避免 useState 不触发重渲
   - 多 tab 同步: 监听 `window.addEventListener('storage', ...)`, 跨 tab 切主题时本地也跟切
   - 拆 `lib/theme-core.ts` (纯函数) + `lib/theme.ts` (hook) — 纯函数没 React 依赖, mjs 端到端能 import 跑真实验证 (lesson #2/#15 同源教训)

4. **全局扫颜色硬编码, 不能只改 `tailwind.config.ts`**
   - `globals.css` 里 `.markdown *` 系列 (pre / blockquote / th / a / hr / strong / code / input checkbox) 全部 hardcode dark hex, **必须**改成 `rgb(var(--color-X))` 引用
   - 锁住防退化: pytest 静态不变量测试扫 globals.css, 11 个 forbidden hex 全部禁止出现
   - `body` / `html` background 和 color 也必须改 var(), 切主题时 body 颜色才变

5. **不变量测试要"双层锁": 静态不变量 + 端到端 mjs**
   - 静态不变量 (test_theme_toggle_invariants.py 17 条) 锁架构: 早期脚本有 / 早期脚本读 localStorage / tailwind darkMode='class' / globals.css 双套变量 / ThemeToggle 挂载 / 不能有硬编码 hex / ...
   - 端到端 mjs (scripts/test-theme-core.mjs 33 条) 锁行为: node 22 `--experimental-strip-types` 真跑, mock DOM + localStorage 验证 `getStoredTheme` / `applyTheme` / `toggleTheme` / `subscribeTheme` 真实行为
   - lesson #2/#15 同源: **单测过 ≠ 真实数据过**。mjs 跑 33 用例捕获了 mock 错位 / 断言数错 / 容错路径漏等多类问题, 单靠 grep 源码字符串发现不了

### 修法位置

- `web/tailwind.config.ts` — `darkMode: "class"`, 所有 colors 改 `rgb(var(--color-X) / <alpha-value>)`
- `web/app/globals.css` — `:root` (light) + `.dark` (dark) 双套变量, 全部 markdown 样式改 var()
- `web/app/layout.tsx` — 早期同步脚本 (themeInitScript) + `suppressHydrationWarning`, viewport 去掉硬编码 themeColor
- `web/lib/theme-core.ts` — 纯函数 (getStoredTheme / setStoredTheme / applyTheme / getCurrentTheme / toggleTheme / subscribeTheme / bumpThemeVersion)
- `web/lib/theme.ts` — re-export 纯函数 + `useTheme` hook (useSyncExternalStore) + `storage` 事件多 tab 同步
- `web/components/ThemeToggle.tsx` — 顶栏 IconButton, lucide Sun/Moon 跟 Settings 同尺寸同位置
- `web/components/MainBoard.tsx` — Settings 旁边挂 `<ThemeToggle />`
- `web/scripts/test-theme-core.mjs` — 33 用例端到端 (mock DOM + localStorage)
- `app/tests/test_theme_toggle_invariants.py` — 17 条静态不变量 + 调 mjs 端到端

## #18. light 模式不能照搬 dark 色阶 (修于 2026-08-01)

### 症状

主题切换 v1 (#17) 交付后, 用户切到 light 模式立刻报:
> "感觉白天模式下左侧整个页面太灰了, 看起来脏脏的"

截图看: 主区背景 `#f5f5f5`, 项目卡片用 `bg-bg-tertiary/30` 叠加半透明 = 实际算下来 `#f1f1f1`, **跟主背景只差 4 个色值** — 卡片完全融在主背景里, 加上 `border-transparent` 没边框, 视觉一片灰白分不清层次。

### 根因 (双重)

1. **照搬 dark 色阶到 light 模式 = 反向失败**。我设计时按 dark 模式的小差值 (`#0a0a0a` / `#141414` / `#1e1e1e`, 差 ~10) 直接照搬, light 模式用 `#f5f5f5` / `#e8e8e8` / `d4d4d4` (差 ~13)。**但** dark 模式 13 个色值差在深色背景上**视觉感受是 ~10**, light 模式 13 个色值差在浅色背景上**视觉感受是 ~4** (浅灰之间人眼敏感度低)。结论: **light 模式需要更大色值差才能达到跟 dark 模式同等的视觉层次**。
2. **半透明叠加吃掉了色差**。`bg-bg-tertiary/30` 30% alpha 叠在主背景上, 实际效果 = 0.3 * 232 + 0.7 * 245 = 242 ≈ `#f1f1f1`, **跟主背景 `#f5f5f5` 只差 4**。dark 模式同样手法 (`#1e1e1e/30` 叠 `#141414`) 算出 ~#181818, 跟 wrapper 差 ~4, 但**视觉上 dark 模式 4 个色值差看着是 5-6, light 模式 4 个色值差看着是 1-2** — 人眼对深色微差更敏感, 浅色微差几乎无感。

### 教训 (4 条)

1. **light 模式色阶要大跨步, 不能照搬 dark**
   - 旧 (v1): light `#f5f5f5` / `#e8e8e8`, dark `#0a0a0a` / `#141414` — 同比例差 13
   - 新 (v2): light `#ffffff` / `#f8fafc` / `#f1f5f9` (slate 系, 跨 20+), dark 保持 `#0a0a0a` / `#141414` / `#1e1e1e`
   - 关键: light 模式用 **slate 蓝调浅灰** 而不是 **纯灰**, 看着"冷干净"不"灰扑扑" (Stripe / Linear / Notion 浅色 dashboard 同套路)

2. **容器用纯白 + 显式 border, 别靠半透明叠加**
   - 旧: `bg-bg-tertiary/30` 半透明 — 叠加效果不可预测, 跟主题色温绑定
   - 新: `bg-bg` 纯白 + `border border-border` (slate-300) — 卡片**显式立**出来, 不依赖半透明
   - lesson: **"白底卡片 + 显式 border" 比 "半透明叠加" 可靠 10 倍**, 后者看着巧妙但实际色差被吃掉

3. **light 模式边框要更深, 不然看不出**
   - 旧: `border-border: #d4d4d4` — 浅灰边框在浅灰背景上几乎不可见
   - 新: `border-border: #cbd5e1` (slate-300) — 跟浅灰背景对比明显, 卡片边界清晰

4. **dark 模式卡片别用 `bg-bg` (= body 色), 会跟 body 融**
   - 修了 light 模式后我顺手把 ProjectCard 改 `bg-bg`, **dark 模式立刻退化** — 卡片 #0a0a0a = body #0a0a0a, 卡片"沉"回去跟 body 融在一起
   - 修法: ProjectCard 用 conditional class `bg-bg dark:bg-bg-tertiary` — light 模式用 bg (纯白), dark 模式用 bg-tertiary (稍亮一档, 比 wrapper 凸)
   - lesson: **"卡片"在 light/dark 模式里"凸的方向"虽然都是"比主区亮"**, 但 dark 模式下 bg = body 色, 不能简单用 bg 当卡片背景, 必须 conditional

### 修法位置

- `web/app/globals.css` — `:root` 块重设 light 色阶 (slate 系: bg #ffffff / bg-secondary #f8fafc / bg-tertiary #f1f5f9 / border #cbd5e1 / border-hover #94a3b8 / fg-secondary #475569 / fg-muted #64748b)
- `web/components/MainBoard.tsx` — ProjectCard 用 `bg-bg dark:bg-bg-tertiary border border-border hover:border-border-hover` (取代旧 `bg-bg-tertiary/30 border-transparent`)

## #27. Tailwind 3 字符串形式的 colors 会被解析, CSS 变量失效 (修于 2026-08-02)

### 症状

v0.3 主题架构落地后, 默认 dark 模式一切正常, 用户从 v0.3.5 开始用了 2 周没反馈。
v0.4.1 (时间线 toggle) 之后用户第一次主动点 ThemeToggle 切 light 模式, 立刻报:
> "现在切换模式整个页面没有变化"

截图看: 点 toggle → 按钮文字翻 (React state 切到 light) → 页面视觉**完全没变**,
body 背景还是 #0a0a0a, 文字还是 #e5e5e5。切 localStorage 清掉重 load, html 拿到
.light class, **仍然没变**。

### 根因 (潜伏型)

`web/tailwind.config.ts` 的 colors 块用了**字符串形式**:

```ts
// v0.3 立 v0.4.1 一直在用
colors: {
  bg: { DEFAULT: "rgb(var(--color-bg) / <alpha-value>)" },
  // ...
}
```

Tailwind 3 看到这种 "rgb(...)" 形式的字符串, 会**走 color parser 尝试提取 RGB 组件**。
提取不到时, 它把 `var(--color-bg)` 替换成**当前作用域里 `--color-bg` 的值**——
而当时 .dark 块的 `--color-bg: 10 10 10` 在全局生效, 所以 `var(--color-bg)` 被
fallback 成 `10 10 10`, 写死到编译产物:

```css
/* 编译产物 (.bg-bg) — 错 */
.bg-bg {
  --tw-bg-opacity: 1;
  background-color: rgb(10 10 10 / var(--tw-bg-opacity, 1));  /* 字面量! */
}

/* 应该是这样 */
.bg-bg {
  --tw-bg-opacity: 1;
  background-color: rgb(var(--color-bg) / var(--tw-bg-opacity, 1));  /* var() */
}
```

所有 14 个 utility (bg×3 / border×2 / fg×3 / accent×2 / success / warning / danger / info)
都被硬编码成 dark 值。切 html class 也好, 改 :root 变量也好, **都没用**——
因为组件层的 class 引用的是编译产物的字面量, 不再走 CSS 变量级联。

### 为什么这个 bug 潜伏了 2 周

- **默认 dark + 硬编码 dark = 视觉一致**: 项目 v0.3 上线时默认 dark, 硬编码
  后的 dark 值跟 :root 里的 dark 值一样, 肉眼无感
- **lesson #18 (light 色阶) 立的测试只锁了源码字符串, 没锁编译产物**:
  `test_theme_toggle_invariants.py` 17 条不变量测试扫 `tailwind.config.ts`
  看是不是 `rgb(var(--color-X)`, **没去 curl 编译后的 CSS 看产物是不是真有 var()**
- **lesson #2 / #15 同源反复犯**: 架构层字符串能 grep, 编译产物要真看

### 教训 (4 条)

1. **Tailwind 3 + CSS variables 必须用函数形式, 字符串形式会被解析**
   - 字符串 `"rgb(var(--color-X) / <alpha-value>)"` → Tailwind 走 color parser,
     `var()` 被 fallback 到当前作用域值, **写死到产物**
   - 函数形式 `({ opacityValue }) => opacityValue !== undefined ? \`rgb(var(--color-X) / ${opacityValue})\` : "rgb(var(--color-X)"` → Tailwind **跳过 color parser**, 直接原样输出
   - 文档: https://v3.tailwindcss.com/docs/customizing-colors#using-css-variables — 唯一正确的写法

2. **不变量测试要锁"编译产物", 不能只锁"源码字符串"**
   - lesson #2 / #15 / #17 / #27 同源反复犯: 我写的 17 条不变量测试全过,
     但编译后 CSS 里没一条产物检查
   - 修法: 加测试 `curl http://localhost:3002/_next/static/css/app/layout.css?${v} | grep -c "var(--color-)"` 必须 ≥ 14 (utility 数)
   - 或者: `parsed.tailwind.config.ts colors.X 不允许 string, 必须 function`

3. **默认值跟 bug 视觉一致时, bug 会被隐藏**
   - lesson #18 立的色阶 (默认 dark + 硬编码 dark) 让 v0.3.5 → v0.4.1 整整 2 周
     bug 看不见
   - 修法: 新功能上线必须**主动切到非默认值验证一遍** (切 light 模式跑一次,
     切英文/中文/暗色... — 每多档手动验一次), 不能默认状态 OK 就当 OK

4. **官方类型不认函数形式时, 局部 `as any` 比改全局类型干净**
   - `Config.colors` 类型签名 `string | RecursiveKeyValuePair<string, string>`,
     没暴露函数形态 (Tailwind 3 .d.ts 漏)
   - 改 `as Config` 全局 any → 丢其他字段类型保护
   - 改 `colors: { ... } as any` 局部 any → 影响面最小, 注释说明 "官方 .d.ts 缺,
     runtime 支持, see Tailwind docs"
   - 同源: lesson #2 也提过, "类型不够时局部 any 优于整体 any"

### 修法位置

- `web/tailwind.config.ts` — colors 14 个 utility 全部改函数形式, `as any` 绕类型
  (官方 .d.ts 缺函数签名, runtime OK; see Tailwind docs 2026-08-02)
- (待补) `app/tests/test_theme_toggle_invariants.py` — 加: 验证编译产物里
  `.bg-bg` / `.text-fg` / `.border-border` 包含 `var(--color-)`, **不能是字面量**
  — 用 `subprocess.run` curl 编译后的 CSS 解析

### 关键诊断命令 (留个底, 下次 30 分钟排查缩到 30 秒)

```bash
# 1. 看 React state 切没切
curl -s http://localhost:3002/ | grep -oE 'data-theme-state="[^"]*"'
# (注: SSR 永远 dark, 这个看 React DevTools)

# 2. 看 html 拿到 class 没
# DevTools → Elements → <html> 看 classList

# 3. 看 CSS 是不是真用了 var()
curl -s "http://localhost:3002/$(curl -s http://localhost:3002/ | grep -oE 'app/layout.css\?v=[0-9]+' | head -1)" | grep -A2 "^\.bg-bg \{$"
# 期望: rgb(var(--color-bg) / ...)
# 错: rgb(10 10 10 / ...) ← 字面量 = bug

# 4. 一次性扫所有 utility
curl -s "http://localhost:3002/_next/static/css/app/layout.css?${v}" \
  | grep -B0 -A2 "^\.bg-bg \{$\|^\.text-fg \{$\|^\.border-border \{$\|^\.bg-accent \{$" \
  | head -20
```

## 关联 Lessons (跨文件)

- lesson #2 (LLM CoT 暴露 + markdown fallback 误执行) — 同源: 架构层能 grep 不够, 行为层得真跑
- lesson #15 (端到端 UX 路径静态分析) — 同源: 单测过 ≠ 真实数据过
- lesson #17 (主题切换架构) — 上游 lesson, 主题架构立得正确, 但 config 写法有个坑埋下了
- lesson #18 (light 色阶) — 同源: 默认值跟 bug 视觉一致时, bug 会被隐藏 (lesson #27 教训 3)
- lesson #25 (成就二次加工 PR 描述) — 同源: 端到端要真验证, 不能只 grep 字符串

## #31. 语义色不能一色多义，弱底色也必须做组合对比测试（修于 2026-08-11）

### 症状

旧的 amber 同时表示 CTA、已选状态、成就闪现和待补提醒。即使用户读得懂文字，
也无法在扫视时分清「可点」「已沉淀」和「需要处理」。成就库的项目卡内再放成就卡，
又让每条资产的视觉重量与项目容器相同，页面显得像深色后台而不是成就库。

### 根因

1. token 只有颜色名，没有产品语义归属；组件直接复用 `accent`，导致暖色含义漂移。
2. 仅检查单个文字/背景色的对比度，忽略软底色嵌套后实际的合成颜色；深色模式尤其
   容易掉到 AA 以下。
3. 把「分组」误实现为「每个层级都加一张卡」，没有区分容器和列表行。

### 教训

1. **token 必须先写所有权，再写颜色。** interaction = indigo 的操作与选中，asset =
   gold 的可复用成就，warning = orange 的风险/缺数据；不能跨角色借色。颜色调整时先
   改 token 层，再由 `getVisualTone()` 给组件提供 treatment。
2. **软底色要有单一允许值表，并验证最终合成对比。** `SOFT_TONE_OPACITIES` 是产品
   唯一允许的透明度；测试需覆盖 light/dark、父表面叠加与 Tailwind 编译产物，不能只
   grep class 或测原色。
3. **卡片用于边界，divider 用于条目。** 成就库保留项目组和质量摘要卡；组内资产与
   时间线是带分隔线的行，信息密度更高且编辑/补全操作仍可清楚定位。
4. **视觉升级先用现有 token 系统，不以渐变或新设计系统替代层级。** 渐变会掩盖状态，
   第三方 DS 会扩大主题与状态回归面；在 CSS variables + Tailwind 已能表达需求时，
   先增强语义、对比和密度。

### 修法位置

- `web/app/globals.css` — `accent` / `asset` / `warning` 的 light/dark token 与
  blue-grey 深色层级。
- `web/tailwind.config.ts` — `asset` 的函数式 CSS-variable colour mapping 和 JIT
  safelist；必须保留 `web/lib/` content scan（见 #27）。
- `web/lib/visual-system.ts` — 角色到 Tailwind treatment 的共享边界与可用软底色。
- `web/components/MainBoard.tsx`、`web/app/achievements/page.tsx`、
  `web/app/report/page.tsx` — 分别消费成就价值、交互和风险角色。
- `web/scripts/test-visual-tokens.mjs` — 角色、编译产物、弱底色和组合对比回归契约。

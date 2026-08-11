---
date: 2026-08-11
slug: visual-language-refresh
title: 视觉语义刷新 — 交互、成就价值与风险分色
status: 现行
supersedes: —
related_lessons: #31 · #27
---

## Changelog: 2026-08-11 视觉语义刷新

把过去同时承担品牌、选中、CTA、成就和提醒含义的暖色拆开，使 Cockpit 更像
一个克制的个人成就工作台，而不是深色后台。

## 决策与落地

| 语义所有权 | Token | 用途 | 不得承担 |
| --- | --- | --- | --- |
| interaction | `accent`（indigo） | 已选控件、编辑焦点、CTA、报告范围/模板 | 成就价值、风险提示 |
| asset | `asset`（gold） | 已沉淀成就、可复用证据、报告可用价值计数 | 选中态、待补数据 |
| warning | `warning`（orange） | 缺数据、待补全、需要处理的风险 | CTA、成就奖励 |

- 保持 `:root` / `.dark` CSS 变量和 `darkMode: "class"`；深色面板调整为
  blue-grey 层级，light/dark 都从同一语义 token 取色。
- `web/lib/visual-system.ts` 是组件层唯一的角色边界：`getVisualTone()` 只接受
  interaction、asset、warning；同角色弱底色只允许已验证的 5%/10% 透明度。
- 主看板的成就闪现、成就库质量/分布指标与报告可复用价值计数归 `asset`；筛选、
  选项和下载等操作仍归 `accent`；数据缺口归 `warning`。
- 成就库保留项目分组与质量摘要两类卡片；组内项目条目和时间线改为 divider rows，
  消除 card-within-card 的重复边框，但不牺牲分组、编辑或补全入口。
- 报告在没有待补条目时使用紧凑恢复摘要；有真实待补数据时仍展示原有可滚动条目和
  「去补全」入口。说明与成就正文提升到 13px，时间戳/小操作继续是元数据字号。

## 取舍

不加渐变：本产品的核心是事实、沉淀和输出，渐变会把注意力从状态和证据转向装饰，
也会降低 light/dark 下的层级可预测性。也不引入第三方设计系统：现有 Tailwind +
CSS-variable token 层已经覆盖这次需要；新增依赖会把现有主题、密度与组件状态的
维护责任外包，反而扩大回归面。

## 防回归与已完成的范围验证

- `web/scripts/test-visual-tokens.mjs` 直接运行角色映射，并编译 Tailwind 临时产物，
  断言 `asset` / `warning` 工具类仍保留 CSS 变量；覆盖同角色软底色、嵌套表面与
  light/dark composited text contrast。当前任务 3 完成时为 **84 passed**。
- 本轮 scoped checks 已通过：visual token contract（84）、achievement stats（64）、
  synthetic report、report readiness、`npx tsc --noEmit` 和 `git diff --check`。
- 没有运行 `next build`，避免污染正在使用的开发产物（lesson #16）。
- 浏览器的 390×844、1280px 和 light/dark 截图验收属于整轮最终验收，尚未在本记录中
  声称已完成。

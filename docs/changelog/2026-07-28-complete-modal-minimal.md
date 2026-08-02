---
date: 2026-07-28
slug: complete-modal-minimal
title: 完成弹窗极简化 A+D (PM 视角 UX 重做)
status: 现行
supersedes: —
related_lessons: #14
---

## Changelog: 2026-07-28 完成弹窗极简化 A+D (PM 视角 UX 重做)

用户原话 (2026-07-28): "我在完成一个任务的时候, 我需要去填写 CV 这一部分以及完成了什么, 就我觉得有点麻烦"。

### 调查 + 根因

旧 `CompleteTaskModal` 是 4 字段全显示 (outcome / cv / reflection / cv_status, 见旧 v1 设计), 核心痛点:

1. **outcome 和 cv 90% 重复** — 弹窗 placeholder 就是同一件事的两种写法
   - outcome: "用户反馈登录 bug 已修复, 无复现, DAU 提升 5%"
   - cv: "定位并修复高优先级登录鉴权 bug, 消除用户阻塞, 当日上线验证"
   - 用户填完 outcome 再写 cv, 本能反应"我不是刚写过了吗"
2. **完成时刻是多巴胺峰值, 4 字段问卷是最差时机** — 心理学问题, 跑过终点让人填表
3. **cv_status 三态让认知再加重一档** — ready / needs_data / pending 大多数用户没空想直接选 ready
4. **价值是"未来兑现"用户当下看不到** — 成就库不主动去的话, 弹窗就是纯成本

**取舍**: "完成即沉淀" 哲学 (task-cockpit 核心) 没错, **错在执行** — 把全部成本压在用户最容易疲劳的那一刻, 又不让用户当下感受到沉淀的价值。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| A1 | **后端: 新增 `POST /api/llm/polish_cv` 端点** | `app/api/llm.py` | body=`{task_title, outcome}`, 返 `{cv, polished}`. LLM 不可用/异常/空返回 → 静默 fallback `完成「${title}」`, 不抛 500. polished=false 标记走了 fallback |
| A2 | **前端: `api.polishCv()` 封装** | `web/lib/api.ts` | 跟其他端点同款 `request<T>()` 包装, 错误透传 |
| A3 | **前端: CompleteTaskModal 砍到 1 必填 (outcome)** | `web/components/CompleteTaskModal.tsx` | 旧 4 字段全显示 → 主流程只剩 outcome 必填, cv 智能预填 `完成「${task.title}」` |
| A4 | **前端: CV 区域加 "✨ 润色" 按钮** | 同上 | 调 `api.polishCv()`, 失败保留原文 cv + warning 提示, 不阻塞提交 |
| A5 | **前端: 高级选项折叠** | 同上 | reflection + cv_status 折叠在"高级选项 (可选)" 默认收起, 不挡视线但还在 |
| D1 | **前端: 全局 Toast 系统** | `web/components/Toast.tsx` (新) + `web/app/layout.tsx` 挂载 | `ToastProvider` + `useToast()` hook, 3 种 variant (success/info/warning), 3.5s 自动关闭, hover 暂停, 上限 3 条并发 |
| D2 | **前端: 完成时弹 toast 庆祝** | `web/components/MainBoard.tsx` + `web/app/today/page.tsx` | 文案 `🎉 已沉淀 · 成就库累计 N 个 ready` + "查看成就库 →" 跳转 `/achievements` |
| A6 | **不变量测试 9 条新增** | `app/tests/test_complete_modal_minimal_invariants.py` (新) | 锁 outcome 必填/cv 不必填/cv 预填/有润色按钮/高级折叠默认收起/submit 条件/自动 focus/走 api.polishCv 封装/失败不阻塞 |
| A7 | **端点测试 9 条新增** | `app/tests/test_api_polish_cv.py` (新) | 锁无 LLM fallback/LLM 异常 fallback/LLM error 返 fallback/正常 polish/引号清理/超长截断/空白返 fallback/missing outcome 422/空 outcome 422 |
| D3 | **不变量测试 8 条新增** | `app/tests/test_completion_toast_invariants.py` (新) | 锁 Toast 组件导出/Provider 在根 layout/MainBoard 弹 toast/今天也弹/自动关闭 3500ms/hover 暂停/上限 3 条/两处入口文案一致 |
| A8 | **lesson #14 立** | `docs/lessons/01-frontend-ux-bugs.md` + `AGENTS.md` 索引 | "完成时刻摩擦" — 4 字段问卷的"完成成本 vs 沉淀价值" 反向设计, 跟 #4 "完成路径堵死" 同源(都是完成路径 UX 失败) |

### 设计决定记录

**A. 砍到 1 必填 vs 留 2 字段分两层**

- 旧版 2 必填 (outcome + cv) 的"分工"是 outcome 自由写, cv 简历润色版 — **理论上**合理, **实践上** 90% 重复
- 选 1 必填 + cv 智能预填 + 润色按钮:
  - 必填项 = 真正"用户独有信息" = outcome (LLM 推不出来)
  - cv 字段 = LLM 主导 (用户可以一键润色, 也可以接受默认 `完成「${title}」`)
  - 用户认知负担 = 1 字段, 跟"完成任务"心智模型匹配
- 旧版 lesson #4 教训"完成路径堵死" 已挡住"不能完成"路径, 新版防"完成太麻烦" 路径 — 两个 lesson 是同一根问题的两个症状

**B. 高级选项默认折叠 vs 全部隐藏**

- 全部隐藏: 用户主动权下降, 不能写 reflection / 改 cv_status
- 选折叠: power user 仍能用, 默认用户看不到 → 主流程 1 字段
- lesson: "可选字段不删, 折叠起来" — 跟 StatusMenu 末尾 blocked/draft toggle 同款思路 (2026-07-22 立)

**C. AI 润色失败 fallback vs 阻塞**

- 阻塞: 润色失败 → 完成失败 → 用户挫败, LLM 偶尔抽风 体验崩
- 静默 fallback: 失败保留原文 cv (用户原始输入), 弹 warning toast 提示, 完成可继续
- lesson: **AI 增强层永远不能在主流程上制造新阻塞** — fallback 优先

**D. Toast 3.5s vs 5s vs 永久**

- 3.5s: 足够读"已沉淀 · 累计 N 个" + 决定要不要点跳转
- 太短 (1-2s): 用户看不清就消失
- 太长 (5s+): 挡住聊天窗/任务列表
- hover 暂停: 用户犹豫时可暂停决策, 不强制 3.5s 内选

**E. 入口文案"🎉 已沉淀 · 成就库累计 N 个 ready" vs "任务已完成"**

- 旧思维: "任务已完成" = 状态通知, 跟系统本身功能重复
- 选"已沉淀 · 累计 N": 把完成动作翻译成"价值获得", 用户当下能感受到在攒家底
- lesson: **完成 toast 不是"操作反馈", 是"价值反馈"** — 完成即沉淀 的"沉淀" 两字用户必须看见

**F. 后端 polish_cv 端点 vs 前端直接调 chat**

- 前端直调 chat 端点: 复用对话基础设施, 但要构造 messages/system 协议 (Anthropic 格式), 维护成本高
- 选独立端点: 协议在后端, 前端只发 `{task_title, outcome}` 拿 `{cv, polished}`, 干净解耦
- lesson: **专用 API 优于通用 chat 端点** — 不复用复杂度, 让每个端点聚焦一件事

**G. 旧 4 字段弹窗架构保留 (高级区) vs 完全删除**

- 完全删除 reflection/cv_status: 旧 power user 流失, 成就库少一个维度
- 折叠保留: 默认用户看不到, power user 仍能填, 后端 schema 0 改动
- lesson: **降级而不是删除** — 把"必须填"降级成"可选填", 用户价值不丢, 摩擦砍掉

### 完成路径 UX 不变量 (防退化)

| 不变量 | 锁哪 | 文件 |
|---|---|---|
| outcome 必填, cv 预填 | modal 必填标记 + useState 初始值 | `CompleteTaskModal.tsx` |
| 有 ✨ 润色按钮 + 调 api.polishCv | "润色" 文案 + `await api.polishCv` | 同上 |
| 高级选项默认折叠 | `useState(false)` + `showAdvanced && (...)` | 同上 |
| Toast 挂根 layout | `<ToastProvider>` 包裹 children | `layout.tsx` |
| 完成必弹 toast + 跳转 | `toast.success(...)` + `router.push("/achievements")` | `MainBoard.tsx` + `today/page.tsx` |
| 两入口文案一致 | 正则提取 `toast.success` 模板, 剥掉 `${}` 插值后必须相等 | 测试断言 |
| polish 失败不阻塞 | `try/catch` + `setPolishError` 不 throw | `CompleteTaskModal.tsx` |

### 字段表 (改完之后)

| modal 字段 | 旧版 (4 必填/选填) | 新版 (1 必填 + 1 智能 + 2 折叠) | 摩擦变化 |
|---|---|---|---|
| `outcome` | 必填 | 必填 | 不变 |
| `cv` | 必填 | **预填** (用户可不管) + 润色按钮 | 必填 → 默认有值 |
| `reflection` | 选填 | **折叠** (默认收起) | 不挡视线 |
| `cv_status` | 三态必选 | **折叠** (默认 ready) | 不挡视线 |

**回归**: 172 → **200** tests pass (+28: 9 polish_cv 端点 + 9 modal 不变量 + 8 toast 不变量 + 2 之前顺手修的 storage 测试). `tsc --noEmit` 0 错误. `npm run build` 10/10 静态页导出通过. 改动 1 后端 + 4 前端 + 3 测试 + 1 layout, 净 +约 600 行 (含 200 行测试), 用户视觉上的"4 字段问卷" 变成 "1 字段 + 1 智能按钮 + 完成 toast 庆祝"。





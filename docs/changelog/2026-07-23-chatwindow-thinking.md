---
date: 2026-07-23
slug: chatwindow-thinking
title: ChatWindow 双「思考中」视觉堆叠修复
status: 现行
supersedes: —
related_lessons: #13
---

## Changelog: 2026-07-23 ChatWindow 双"思考中"视觉堆叠修复 (用户报告)

用户反馈: "红框区域 (对话框最下方) 总是有两个『思考中...』上下叠"。截图清楚显示两个一样的 loading indicator 堆在一起。

### 调查 + 根因

代码里有**两个独立的"思考中"渲染点**:
1. **顶层 `{loading && <思考中...>}` 块** — `web/components/ChatWindow.tsx` 旧 line 485-494, `Sparkles 14px + "思考中..."`
2. **消息气泡内 EventsView** — `web/components/ChatWindow.tsx` line 739-744, `streaming && events.length === 0` 时返回"思考中…"

时序: `useChatStream.send()` 里 `setMessages([..., userMsg, agentMsg])` (line 69) 之后立即 `setLoading(true)` (line 70), 同步执行 — 所以 **`loading=true` ⟺ "messages 里有 streaming agent message" 永远同时为真**, 顶层 loading 跟消息气泡内 EventsView 必然一起出现。

历史原因: 2026-07-09 最早版 ChatWindow 只有顶层 loading 框; 2026-07-20 重构抽 useChatStream hook, 新增 EventsView 处理 stub message (`events=[] + streaming=true`) 也加"思考中…" fallback — 两者并存 = 必然重复, 一直没人发现。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **删 ChatWindow 顶层 `{loading && (...思考中...)}` JSX 块** | `web/components/ChatWindow.tsx` 旧 line 485-494 | `loading` state 保留 (仍用于: auto-scroll deps、input/button disabled) — 只删那块 JSX |
| 2 | **不变量测试 2 条新增** | `app/tests/test_chat_input_invariants.py` | `test_no_top_level_loading_thinking_indicator` (锁住"messages.map 之后到输入区之前不能出现 `{loading && (` 块, 也不能出现『思考中』 文案") + `test_thinking_text_appears_only_inside_message_bubble` (锁住『思考中』只允许出现在 AgentMessageContent 退化路径 + EventsView 函数体内") |
| 3 | **新增 lesson #13** | `docs/lessons/01-frontend-ux-bugs.md` + `docs/lessons/README.md` 索引 + `AGENTS.md` lessons 索引 | 同 lesson #11 (TaskRow 4 个 ▾ 上下叠) 同源 — "同一个信号在两个地方渲染" 的视觉堆叠问题 |

### 设计决定记录

- **删顶层 vs 删气泡内**: 选删顶层, 因为 **EventsView 的"思考中…"是 stub message 的视觉表达 — 跟消息气泡是同一组件, 位置天然正确, 不需要专门的状态字段来同步**。顶层那个 loading 框需要单独的 `loading` 状态字段 + 额外的 JSX 块, 是历史的"外挂式 loading", 删掉最干净
- **不删 `loading` state**: 仍需要它做 (a) auto-scroll effect 的依赖 (line 239), (b) input/button disabled (line 538/548/552)。**只删 UI 块, 不删数据**, 改造成本最小
- **不变量测试锁"位置"不只锁"内容"**: 旧测试只验证"EventsView 有思考中文案" (字符串存在), 没验证"其他地方没有思考中文案"。新加的两条不变量专门锁位置 — 防退化
- **lesson #11 同源教训**: 同一个项目里"视觉堆叠" 已经出过 1 次 (#11 修于 2026-07-21), 这次 #13 是第 2 次。看到"两个看起来一样的元素" 就要触发"为什么有两份?" 的反射

**回归**: 170 → **172** tests pass (+2 新不变量; 其他 priority 套件 0 变化). `tsc --noEmit` 0 错误. 改动 1 文件删 10 行 + 1 文件加 ~70 行测试, 净 +60 行, 但用户视觉上的"红框两个思考中" 变成 "红框一个思考中"。


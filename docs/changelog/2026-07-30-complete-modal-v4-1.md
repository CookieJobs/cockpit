---
date: 2026-07-30
slug: complete-modal-v4-1
title: 完成弹窗 v4.1 — 按钮位置 UX + 分类器盲点修复
status: 现行
supersedes: v4 部分
related_lessons: #15
---

## Changelog: 2026-07-30 完成弹窗 v4.1 — 按钮位置 UX + 分类器盲点修复 (用户实测 4 轮反馈)

用户原话 (2026-07-30 上午): "润色按钮会让用户以为润色的目标是「CV」而不是「结果描述」" + "修登录鉴权 bug" 走 generic 引导（lesson #15 盲点）。

### 调查 + 根因

**问题 1：按钮位置 UX 反模式**

- 旧设计：润色按钮在 CV 框**右侧**（"CV 成就陈述  动词开头, 含结果/影响 [...] [✨ 润色]"）
- 用户认知：按钮 = 操作 CV 框（视觉上贴着 CV）
- 实际行为：润色流程是 **outcome → CV**（读 outcome 写 CV，按钮的实际目标是 outcome）
- 冲突：用户点按钮期待看到"CV 框变化"，但实际看到的是"outcome 末尾追加追问"——按钮位置和按钮目标不一致，UX 反模式

**问题 2：分类器盲点（lesson #15 单测通过但真实数据失败）**

- 用户实测任务：修登录鉴权 bug / 写完 Q3 述职草稿 / 周末写小红书选题 / 写周报 / 整理述职材料
- 旧 fix 正则要"修复/修好/修完" 复合词，**单独的"修"字**漏匹配
- 旧 artifact 正则只覆盖"PRD/文档/PPT"等明确制品词，**"周报/选题/材料"**漏匹配
- **\b 在中文里不工作**：`/\b修\b.../i` 跟 "修线上问题" 中间隔了字符时不匹配
- 旧 discussion 关键词"述职"导致 "整理述职材料" 误走 discussion（artifact 应该优先）

**问题 3：润色按钮 disabled 视觉太弱**

- 旧：`disabled:opacity-40` × `bg-accent/15` ≈ 6% 透明——视觉上跟 enabled 几乎一样
- 用户看不出来按钮是灰的

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **润色按钮位置改** | `web/components/CompleteTaskModal.tsx` | 从 CV 框旁 → outcome 框**下方**（紧贴行动目标） |
| 2 | **加流向提示** | 同上 | 按钮行左侧 "↓ 改写成下方 CV 框 · 先填结果描述"（outcome 空时追加后半句） |
| 3 | **CV 框 label 明确标 output** | 同上 | "CV 成就陈述  AI 润色结果 · 可手动改"（区分 input vs output） |
| 4 | **disabled 视觉改强对比** | 同上 | `bg-bg-tertiary text-fg-muted`（灰底灰字）替代 `opacity-40` 衰减 |
| 5 | **引导卡片提示语更新** | 同上 | "点下方" → "点上方「结果描述」旁的"（按钮位置同步） |
| 6 | **分类器彻底重构** | `web/lib/taskGuidance.ts` | 改"动作+产物"配对 + 移除 \b + 扩展 artifact 关键词 (周报/月报/季报/材料/选题/文案/笔记/日志/分享) + 扩展 fix 关键词 (崩溃/闪退/故障/超时/宕机/卡顿/泄露/泄漏/exception/crash/timeout/500/404) + 扩展 discussion 复合会议 (复盘会/评审会/对齐会/分享会/讨论会/kickoff) |
| 7 | **端到端测试脚本** | `web/scripts/test-task-guidance.mjs` (新) | 21 个用户真实任务标题跑真实 `classifyTaskTitle` 函数，21/21 全过 |
| 8 | **pytest 调 node 端到端** | `app/tests/test_complete_modal_minimal_invariants.py` | 用 subprocess 调 mjs，跨回归锁住真实分类不退化 |
| 9 | **按钮位置不变量 4 条** | 同上 | 锁 outcome < button < cv 物理顺序 + 流向提示字样 + CV 框 label 标 output + CV 框后无第二按钮 |
| 10 | **lesson #2 强化** | `docs/lessons/02-llm-pitfalls.md` | 加 polish_cv 端点 M3 CoT 污染实战 + 4 路径修法 + "每加 LLM 端点都要端到端实测" 教训 |
| 11 | **lesson #15 强化** | `docs/lessons/01-frontend-ux-bugs.md` | 加"按钮位置 UX 反模式" + "关键词盲点" + "端到端测试方法论" 3 个子教训 |

### 设计决定记录

**A. 按钮位置 vs 文案 vs 流向提示（三选一还是三选三）**

- 单选位置：用户能看出"按钮在 outcome 旁" = 操作 outcome，但 CV 框被"抛"在下面，缺少视觉关联
- 单选文案：把"润色"改成"AI 改写 outcome 到 CV"——文案太长，按钮变宽，破坏 layout
- 单选流向：CV 框加 "👇 来自上方 outcome" 提示——仍然把按钮留在 CV 旁，根因没解决
- **三选三**：按钮移到 outcome 下方 + 文案保留"润色" + 加"↓ 改写成下方 CV 框"流向。位置是根因解决，文案和流向是辅助冗余——**任一单独不够，三个一起才稳**

**B. 润色按钮 disabled 视觉：强对比 vs opacity 衰减**

- opacity 衰减（`opacity-40` × `bg-accent/15`）：叠加后几乎透明，视觉上"没灰" → 用户看不出不可点
- 强对比（`bg-bg-tertiary text-fg-muted`）：灰底灰字，跟 enabled 时的 accent 黄色对比强烈 → 一眼看出
- 教训：**"disabled" 视觉要主动设计，不能用 enabled 态叠加属性实现**。enabled 是什么色，disabled 应该是该色的"反色"或"灰阶"，不是该色"透明"——透明在大多背景上都看不出

**C. 分类器：动作+产物 配对 vs 单一关键词**

- 单一关键词（任意"修"字都走 fix）：误匹配"修文档""修语法"（其实是 artifact）
- 单一关键词（任意"文档"都走 artifact）：误匹配"看文档"（generic）
- **动作+产物配对**：必须有"写/整理/制作"等动作 + "文档/PPT/材料"等产物。**两个条件 AND**，避免单关键词误匹配
- 性能：跟单一关键词比，每个标题多 1 次 regex test，但分类器只跑一次（useMemo 缓存 task.title），开销 < 0.1ms

**D. 端到端 mjs 测试 vs pytest 静态分析**

- 旧 pytest 静态分析（test_complete_modal_minimal_invariants.py）：断言"fix 关键词含 'bug'""artifact 关键词含 'prd'"等——**只验关键词存在，不验函数行为**
- 新 mjs 端到端（scripts/test-task-guidance.mjs）：用 node 跑真实 `classifyTaskTitle` 函数，断言"修登录鉴权 bug → fix"——**验真实函数对真实数据的真实分类**
- 旧 pytest 漏过的盲点（"修登录鉴权 bug" 走 generic）端到端全捕获
- lesson：**单测通过 ≠ 真实数据通过**。每加一个分类器/解析器/LLM 工具，端到端测试是必做的，不是 nice-to-have

**E. 中文 \b 不工作的踩坑**

- 旧 fix 正则用 `/\b修\b.*?(bug|问题|...)/i`——预期"修"字独立成词
- 实际：中文没有 word boundary，`\b` 在 "修" 和 "线" 之间不匹配（因为都是"字"非"word"）
- 修法：直接去掉 `\b`，让 regex 在字符间自由匹配
- 教训：**中文场景下用 \b 前要先验证**，很多 JS 正则教程都默认英文环境

### 字段表（v4.1 改造后的弹窗布局）

| 区域 | 旧 v4 (2026-07-30 凌晨) | 新 v4.1 (2026-07-30 上午) | 变化 |
|---|---|---|---|
| 润色按钮位置 | CV 框旁 | outcome 框下方 | **位置改** |
| 流向提示 | 无 | "↓ 改写成下方 CV 框" | **新加** |
| CV 框 label | "动词开头, 含结果/影响" | "AI 润色结果 · 可手动改" | **明确 output** |
| 引导卡片提示 | "点下方 ✨ 润色" | "点上方「结果描述」旁的 ✨ 润色" | **指代更新** |
| 润色按钮 disabled | opacity-40 × accent/15 ≈ 6% 透明 | 灰底灰字 bg-bg-tertiary text-fg-muted | **强对比** |
| 分类器 | 4 类 + 复合词优先 | 4 类 + 动作产物配对 + 移除 \b + 扩展关键词 | **重构** |
| 测试方法 | pytest 关键词字符串覆盖率 | pytest 关键词 + mjs 端到端 21 case | **端到端补** |

**回归**: 234 → **246** tests pass (+12: 5 按钮位置/流向不变量 + 1 disabled 改写 + 1 端到端分类 + 5 polish_cv 端点强化测试). `tsc --noEmit` 0 错误. 端到端 mjs: 21/21 用户真实任务标题分类全过. 改动 2 前端文件 + 1 新前端文件 + 2 改测试 + 1 新 mjs 脚本 + 2 lesson 强化, 净 +约 400 行.


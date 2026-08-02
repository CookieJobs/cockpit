---
date: 2026-07-30
slug: complete-modal-v4
title: 完成弹窗 v4 — 任务引导卡片 + AI 追问 (动作≠价值 解药)
status: 现行
supersedes: —
related_lessons: #15
---

## Changelog: 2026-07-30 完成弹窗 v4 — 任务引导卡片 + AI 追问 (动作≠价值 解药)

用户原话 (2026-07-29 23:50): "如果我在项目中的一个任务是「完成 PRD」, 那么我的「结果描述」以及「CV 成就陈述」要怎么写呢?"

### 调查 + 根因

lesson #14 (2026-07-28) 把完成弹窗砍到 1 必填 + 智能预填 + 润色按钮, 解决了"完成时刻摩擦大"。但**新痛点浮出水面**: "摩擦没了, 但用户还是不会写" — outcome 写啥? cv 写啥? "任务标题已经说了啊"

**根因 — "动作 ≠ 价值" 认知错位**:
- 任务标题 = 动作 (写 PRD / 修 bug / 开会)
- outcome / cv = 价值 (为 X 团队输出 PRD 覆盖 18 个场景 / 修复 bug 影响 5% DAU / 推动 5 个决策)
- **用户当下大脑卡在"动作记忆"**, 调不出"为什么有价值" 的价值记忆
- 弹窗只"收集字段" 不"帮用户回忆价值" — 1 个 textarea 等用户主动写, 跟"认知科学 recall > recognition 难 10 倍" 撞
- placeholder 给"修 bug" 示例 → "写 PRD" 用户看了心想"我又不是修 bug" → 自我怀疑 + 摩擦叠加
- LLM 润色拿到 1-2 字抽象 outcome, 即便尽力润色也只能返 `完成「title」` 兜底, 因为**没追问机制**主动问"给谁看 / 解决什么"

**取舍**: 旧 lesson #14 "降级" (4 字段 → 1 字段) 是对的方向, 但光降级不够, **要再加 2 件事**:
1. **任务标题分类 → 引导卡片** (前端, 纯函数) — 给"识别型" 提示, 帮用户从 4 维度里挑
2. **AI 追问** (后端 prompt + 前端 chip) — 让 LLM 主动问 1-2 个关键问题, 形成"outcome → 追问 → 补全 → 再润色" 对话闭环

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **新建 `web/lib/taskGuidance.ts`** | 新文件 | 5 类 (artifact/fix/discussion/research/generic) × 5 字段 (emoji/label/4 dimensions/placeholder/2-3 followUps). 纯前端函数 `classifyTaskTitle(title)` |
| 2 | **CompleteTaskModal v4 改造** | `web/components/CompleteTaskModal.tsx` | outcome 下方加引导卡片 (默认展开可关) + 动态 placeholder + 追问 chip + `appendFollowUp` 函数 |
| 3 | **后端 `polish_cv` 端点增强** | `app/api/llm.py` | prompt 让 LLM 必要时返 JSON `{cv, follow_up_questions}`, 加 `_parse_llm_json_output` 鲁棒解析 (严格 JSON / ``` 包装 / 纯文本 3 路径) |
| 4 | **后端 `PolishCvResponse` schema 加 `follow_up_questions`** | 同上 | `list[str] = Field(default_factory=list, max_length=3)`, fallback 路径也返空数组 (前端 `length > 0` 判断依赖此不变量) |
| 5 | **前端 `api.polishCv` 类型同步** | `web/lib/api.ts` | 返回类型加 `follow_up_questions?: string[]` |
| 6 | **后端测试 9 条新增** | `app/tests/test_api_polish_cv.py` | JSON 含 questions / 空 questions / ``` 包装解析 / 纯文本 fallback / 空 cv fallback / 字段必存在 (3 路径) / max 3 截断 / 异常 / 无 LLM |
| 7 | **前端不变量 9 条新增** | `app/tests/test_complete_modal_minimal_invariants.py` | import taskGuidance / 分类调用 / placeholder 动态 / 引导卡片 / 追问保存 / 追问渲染 / appendFollowUp / 5 类覆盖 / PRD 关键词识别 |
| 8 | **lesson #15 立** | `docs/lessons/01-frontend-ux-bugs.md` | "完成弹窗「动作≠价值」— 抽象任务不会写" |

### 设计决定记录

**A. 引导卡片位置 (outcome 下方) vs 标题区 (顶部)**

- 顶部: 显眼, 但挡视线, 用户还没填 outcome 就被一堆提示打脸
- 下方: 填到一半时**自然看到** — 用户最需要提示的时刻 = 正在写但卡住的时刻
- 选下方: 跟 2026-07-20 /today 晨间 ritual 的"做之前想清楚" 哲学一致

**B. 引导卡片默认展开 vs 默认折叠**

- 折叠: 干净, 但用户不知道有这玩意儿, 等于没做
- 选展开: 首次打开弹窗时**主动推** 4 维度, 用户不想看可一键关 (`showGuidance` state)
- lesson: **教育型 UI 的关键 = 主动推** — 用户不知道有更好方法时, 默认隐藏 = 等于没做

**C. 5 类任务 vs 10+ 细类**

- 10+ 细类: 分类准, 但维护成本爆炸 (每类要写 placeholder + 维度 + 追问), 关键词撞规则难调
- 选 5 类: artifact / fix / discussion / research + generic 兜底, 覆盖 Cockpit 实际 80% 任务
- generic 兜底避免"分类失败" 把弹窗搞复杂, 用户用 generic 也能拿到通用引导

**D. 后端追问 vs 前端追问**

- 前端追问: 纯前端函数, 无 LLM 依赖, 但追问是"硬编码模板" — 跟任务标题/项目上下文无关
- 选后端追问: LLM 看到 task_title + outcome 后能**生成针对性追问** ("完成 PRD" → "给谁看？评审结果？" 不是泛泛"补充细节"), 质量高一个量级
- lesson: **AI 增强型追问 = 跟任务上下文强相关**, 硬编码模板永远追不上 LLM 实际用法

**E. JSON 严格格式 vs 鲁棒解析**

- 严格: LLM 必须返 JSON, 否则 422/500. 但 LLM 不一定严格返 (有时返 ```json 包装, 有时返纯文本)
- 选鲁棒: `_parse_llm_json_output` 处理 3 种情况. 纯文本走老路径 (整段当 cv + questions=[]), 不破坏现有 LLM 行为
- lesson: **AI 输出的鲁棒性设计 = 永远有"老路径" 兜底** — 这次 LLM 严格返 JSON 是新能力, 但纯文本兜底是底线, 两条路径都要测

**F. 追问 chip 点追加 (用户回答) vs 追问 chip 点直接生成答案**

- 追问 = 补全 outcome 的种子, 不是答案本身 — 用户应该自己写答案
- 选追加: 点 chip 把 "【这份是给谁看的？】" 追加到 outcome 末尾, 用户接着打字 "给产品/设计/开发三方"
- 如果点 chip 直接生成答案, 容易变 LLM 替用户编数据 (违反"事实原则" — 不编数据/影响)
- lesson: **追问机制 ≠ 答案机制** — AI 提问, 人回答, 保持"事实来自用户" 的不变量

**G. 追问卡片位置 (cv 框上方) vs 弹窗顶部**

- 顶部: 跟引导卡片撞, 用户被两次提示夹击
- cv 框上方: 上下文正确 (用户在准备润色时看到追问) — **追问只在 polish 完之后才出现**, 时机刚好
- 选 cv 框上方: 跟"主动推 + 时机" 一致 — 引导卡片主动推 (用户还没填), 追问卡片时机推 (用户刚润色完)

### 字段表 (v4 改造后的弹窗)

| 区域 | 旧 v3 (2026-07-28) | 新 v4 (2026-07-30) | 变化 |
|---|---|---|---|
| outcome placeholder | 硬编码 "用户反馈登录 bug 已修复..." | 动态 `guidance.placeholder` (按任务类型) | **类型感知** |
| 引导卡片 | 无 | outcome 下方, 5 类 emoji + label + 4 维度 chip | **新加** |
| AI 追问 | 无 | cv 框上方, follow_up_questions 渲染为可点 chip | **新加** |
| appendFollowUp | 无 | 点追问 chip → 追加到 outcome 末尾 + 消费追问 | **新加** |
| 后端 prompt | 纯文本润色 | JSON {cv, follow_up_questions} | **结构化** |
| response schema | {cv, polished} | {cv, polished, follow_up_questions} | **新字段** |

**回归**: 212 → **234** tests pass (+22: 9 后端 polish_cv + 9 modal 不变量 + 4 taskGuidance 静态). `tsc --noEmit` 0 错误. `npm run build` 10/10 静态页导出通过. 改动 1 后端 + 1 新前端文件 + 2 改前端文件 + 2 改测试 + 1 新 lesson, 净 +约 700 行, 用户视觉上的"4 字段问卷" 变成 "1 必填 + 任务类型引导 + 智能追问 + 再润色 对话闭环"。

# Cockpit — Agent Notes

> 项目级记忆，只在 `cockpit/` 这个项目成立。给后面接手 / 跨时间回看的 agent 用。

## 📜 AI 工作必读（最高优先级）

**任何 AI Agent 进入本项目，在动手之前必须先读** [`.ai/AI_CTO.md`](./.ai/AI_CTO.md) **（AI 宪法 v1）**。

> AI 在 Cockpit 中是 **AI CTO**，不是 Coding Assistant。理解业务、给方向、做决策、主动发现技术债与产品机会，是默认职责。

读完宪法再按需深入：

| 文件 | 何时读 | 性质 |
|---|---|---|
| [`.ai/AI_CTO.md`](./.ai/AI_CTO.md) | **必读** | 宪法 — 角色、边界、不可妥协的原则 |
| [`docs/GOAL.md`](./docs/GOAL.md) | **必读** | 产品目标 — 哲学、路线、差异化 |
| [`docs/architecture/ai-native-architecture-v1.md`](./docs/architecture/ai-native-architecture-v1.md) | 改 AI 子系统前 | 操作系统层 — 抽象层、接口契约、不变量 |
| [`docs/harness/achievement-distillation-harness-v1.md`](./docs/harness/achievement-distillation-harness-v1.md) | 改成就蒸馏能力前 | Capability 评估契约 — 指标、不退化下限 |
| [`docs/lessons/`](./docs/lessons/README.md) | 写代码/做 UX 前 | 历史踩坑 — 27 条已修过的真实教训 |

---

## 🎯 当前目标（2026-08-02 启动）

**主目标**：把 cockpit 打造成 **"AI 工作流记忆 → 履历生成 OS"** — 一次沉淀，多次输出。

完整目标档 → [`docs/GOAL.md`](./docs/GOAL.md)（必读）

**快速理解三件事**：
1. **产品定位**：服务**人**（不是服务 agent）— 这是跟 mem9.ai 的核心差异点
2. **核心哲学**：成就库是单一数据源，周报/月报/年终/CV 是不同模板视图
3. **当前版本**：v0.2 起点，**下一个动作是 v0.3 沉淀智能化**

**Agent 在本项目的角色**：产品专家 + 技术专家 + 差异化顾问 + 打工人本人。详见 `docs/GOAL.md`。

---

## 项目一句话

本地优先的个人项目驾驶舱（FastAPI + Next.js 15），自然语言建项目/任务，完成时沉淀成 achievement 资产。

## 核心路径

- **后端入口**：`app/main.py`，启动 `uvicorn app.main:app --reload --port 7842`
- **前端入口**：`web/`（Next.js App Router），启动 `npm run dev`
- **DB**：`~/.cockpit/cockpit.db`（SQLite）
- **LLM 配置**：DB `settings` 表 key=`llm_config` 优先于 `.env`

## 踩过的坑（已修，但教训值得记）

完整 lessons 已拆到 [`docs/lessons/`](./docs/lessons/README.md) — 按主题分文件管理（2026-07-20 立）。

| # | Lesson | 文件 |
|---|---|---|
| 1 | TaskRow 二次确认 UX bug | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 2 | LLM CoT 暴露 + markdown fallback 误执行 | [02-llm-pitfalls.md](./docs/lessons/02-llm-pitfalls.md) |
| 3 | FastAPI simple type 参数 body 丢失 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 4 | TaskRow 状态机循环堵死"完成"路径 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 5 | "低" 优先级色点不可见 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 6 | 端到端 UX 路径静态分析测试方法论 | [04-testing-strategy.md](./docs/lessons/04-testing-strategy.md) |
| 7 | `make setup` 引导歧义 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 8 | Python 3.11 + greenlet 双重坑 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 9 | `NEXT_PUBLIC_API_BASE` 没设 → 前端 fetch 静默打错端口 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 10 | `build_snapshot` 漏传 description → 前端永远看不到 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 11 | TaskRow 4 个 ▾ 上下叠视觉堆叠 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 12 | 整行 click = 完成 反直觉 (v2 推翻) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 13 | ChatWindow 顶层 loading 跟消息气泡"思考中"重复 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 14 | 完成弹窗 4 字段问卷摩擦 → 砍到 1 必填 + 智能润色 + toast 庆祝 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 15 | 完成弹窗「动作≠价值」— 抽象任务不会写 → 任务标题分类引导 + AI 追问 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 16 | `next build` 污染 dev server `.next/` → 样式全丢 → 跑回归用 tsc 不要用 build | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 17 | 主题切换架构 (CSS variables 双套 + 早期同步脚本防 FOUC) | [05-theme-system.md](./docs/lessons/05-theme-system.md) |
| 18 | light 模式不能照搬 dark 色阶 (slate 蓝调浅灰 + 显式 border, 不用半透明叠加) | [05-theme-system.md](./docs/lessons/05-theme-system.md) |
| 19 | `new Date("YYYY-MM-DD")` 时区 bug — "今天" 显示成"明天" (parseLocalDate 工具修复) | [06-timezone.md](./docs/lessons/06-timezone.md) |
| 20 | TaskRow "挂了 N 天" + 新用户"反讽"空状态 (新用户冷启动引导) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 21 | /today 跟主页 FocusSection 重复, 删 /today (重复入口不保留) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 22 | task 保留 (不删) — "我今天干的活不见了" 修复 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 23 | 完成沉淀 LLM 追问 + 周月提醒 (基础架构立, follow-up UI 待补) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 24 | "今日聚焦" 用户无控制权 → 承诺机制 (localStorage + 进度条) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 25 | 成就二次加工 — PR 描述生成 (端到端 + LLM fallback) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 26 | 新用户 Onboarding — 3 步引导 modal (首次访问 1s 弹) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 27 | Tailwind 3 字符串形式 colors 被解析, CSS 变量失效 (主题切不动) | [05-theme-system.md](./docs/lessons/05-theme-system.md) |

新增 lessons 写到 `docs/lessons/` 对应主题文件, AGENTS.md 入口只放索引（保持主文件轻量）。

## 易踩但还没炸的隐患

### `add_task` 幂等检查被 LLM 依赖

`tools.py` 里 `add_task` 做了同项目+同名的幂等检查（返回 existing），但 system prompt 写"不要依赖这个防线"。如果 LLM 看到同名项目/任务时没先 `list_projects` / `list_tasks` 就直接 `add_task`，会触发幂等但**产生静默去重** — 用户的预期可能是"在已有项目下加新任务"而不是"加了个和已有同名的任务"。后端工具层面没问题，前端 prompt 工程是关键。

### `delete_project` 不可逆 + 已有二次确认

`chat_engine.py` 的 system prompt 里写了二次确认流程（要先 list 找到 id → 问用户 → 等明确确认 → 才调 delete_project）。**不要去掉这个确认** — 删项目会清空其下所有任务，不可逆。

## LLM 后端约定

5 个后端（anthropic / deepseek / minimax / openai / custom），deepseek / minimax / openai / custom 都走 `OpenAIClient`（`app/llm/openai.py`）。**这意味着**：

- DeepSeek R1 / MiniMax M3 的 CoT 走 `choice.message.content` 字段（不是 `reasoning_content`），必须 strip
- 不同模型的 tool calling 兼容性差异大，遇到 fallback 路径问题时优先看 `OpenAIClient` 的 tool schema 转换

## 测试

- 后端：`pytest app/tests/ -v`（**294 passed, 1 skipped** — 2026-08-01 主题切换后）
- 前端类型：`cd web && npx tsc --noEmit`
- 端到端 mjs：`node --experimental-strip-types web/scripts/test-theme-core.mjs`（主题切换 33 用例真跑 `lib/theme-core.ts` 真实函数）
- 改 Python 前必须 `rm -rf app/llm/__pycache__` 否则 uvicorn `--reload` 不生效
- 跑回归**不要**用 `next build` — lesson #16：dev server 在跑时 build 会污染 `.next/` 致样式全丢。常用组合是 `tsc --noEmit` + 后端 `pytest`

## 设计哲学：对话驱动 vs 看板 inline edit 的边界（2026-07-16 立）

Cockpit 跟 task-cockpit skill 是同源项目，但**产品形态不同**。task-cockpit 是"看板只读 + 一切修改走对话"，cockpit 是"看板可 inline edit + 对话可生成"。这两种模式各有取舍，**不要混用**：

### 看板 inline edit 适用场景（高频、轻量、原子）

- 改优先级（点色点 → 弹小菜单选 高/中/低）
- 改 due（点 due 标签 → 弹 date input）
- 改 status（点状态下拉 → 选 未开始 / 进行中；选"完成 ✨" 弹 modal 沉淀成就）
- 改标题（双击 → inline input）
- checklist 增删改（行内勾选 / 行内加）

**理由**：用户想"调一下"的时候，说话比点慢 10 倍。这些操作都是单字段、低风险、原子。

### 对话驱动适用场景（低频、需要 LLM 上下文）

- 拆任务（"包括 A、B、C" → 一次性建多个）
- 改 description（长文本，需要 LLM 帮我组织）
- 完成任务（4 字段沉淀：outcome / cv / reflection / cv_status — agent 生成 cv）
- 删除项目（不可逆 + 需要二次确认）
- 生成周报 / 述职 / 复盘（agent 从成就库组织）
- 倒事："我接了个 App 改版，要改登录页、加埋点、还要灰度发布"（一句话拆出 1 项目 + 3 任务）

**理由**：这些操作要么需要"反脆弱"（二次确认 / undo 兜底），要么需要"语义理解"（一句话拆 N 任务），LLM 才能干好。

### 完成即沉淀 — 4 字段 UX 铁律

`web/components/CompleteTaskModal.tsx` 是 4 字段沉淀弹窗，**不要**用 `cv: \`完成「${title}」\`` 凑数 — 后端 schema 和 LLM 工具都为这 4 字段服务：

- `outcome` 必填（用户描述的结果）
- `cv` 必填（agent 生成的简历级成就陈述，**默认预填 `完成「${title}」` 兜底，但用户必填 outcome 后必须改**）
- `reflection` 可选（不强迫 — task-cockpit SKILL.md 第 ② 步明确 "复盘可选"）
- `cv_status` ready / pending 二选一（ready 立刻能用，pending 挂起后续在成就库补全后升级）

**所有完成入口都走 modal**（看板 status 按钮、FocusItem 单击、TaskRow 整行、状态下拉"完成 ✨"、对话 complete_task 工具）— 不要让凑数 cv 绕过去。

## Changelog

完整 Changelog 按主题/日期拆到 [`docs/changelog/`](./docs/changelog/README.md)（2026-08-01 立拆分原则，AGENTS.md 1300+ 行 → 200 行）。

**速查**：
- **现行版本**（18 个）按时间倒序在 [docs/changelog/README.md](./docs/changelog/README.md) 索引
- **推翻链速查**：
  - StatusMenu v2 (2026-07-17) → v3 推翻 (2026-07-21) → 短进度条 (2026-07-22) → 状态融合 (2026-07-22)
  - 完成弹窗 极简化 A+D (2026-07-28) → v4 (2026-07-30) → v4.1 (2026-07-30)
- **被推翻（别照着改）**：2026-07-17 StatusMenu v2 — 看 v3 推翻原因

**最新 3 条**（最近开发热乎期，仅这 3 个常读）：
- [2026-08-01 时区 bug 修复 (lesson #19)](./docs/changelog/2026-08-01-timezone-fix.md)
- [2026-08-01 主题切换 (light / dark) v1](./docs/changelog/2026-08-01-theme-toggle.md)
- [2026-07-31 拖动排序 (项目 + 任务) v1](./docs/changelog/2026-07-31-drag-reorder.md)

更老的 Changelog（2026-07-30 之前）都是考古，按需查表即可。

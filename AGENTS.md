# Cockpit — Agent Notes

> 项目级记忆，只在 `cockpit/` 这个项目成立。给后面接手 / 跨时间回看的 agent 用。

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

- 后端：`pytest app/tests/ -v`（66 tests）
- 前端类型：`cd web && npx tsc --noEmit`
- 改 Python 前必须 `rm -rf app/llm/__pycache__` 否则 uvicorn `--reload` 不生效

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

## Changelog：2026-07-16 借鉴 task-cockpit 8 项

参考 [CookieJobs/task-cockpit](https://github.com/CookieJobs/task-cockpit) 的设计细节，做的 8 项改造。**后端 100% 早已完备**（nextAction / blocked / draft / cvStatus / undo / focus / 14 工具），主要是前端 visual / UX 补齐。

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **4 字段完成弹窗** | `web/components/CompleteTaskModal.tsx` (新) + MainBoard 挂载 | 取代 `cv: 完成「${title}」` 凑数 |
| 2 | **状态机单击循环** (○ ↔ ◐) | MainBoard TaskRow `cycleStatus` + Play 按钮 | 修复了"无法切到进行中"的旧 bug (此版已被 v2 下拉替代, 见下) |
| 4 | **项目 deterministic emoji** | `lib/api.ts` `projectEmoji` + MainBoard ProjectCard | 50 emoji 池子，hash 选 |
| 5 | **任务"挂起 N 天"** | `lib/api.ts` `taskAgeDays` + MainBoard TaskRow meta | 阈值 2 天 |
| 6 | **"今天已完成" 折叠区** | MainBoard DoneTodaySection | 用上 snapshot.done_today 旧数据 |
| 7 | **AGENTS.md 设计哲学段** | 本文件 | 写清对话驱动 vs inline edit 边界 |
| 8 | **轮询 diff 优化** | （无需改） | SWR 自带 ETag，验证过 |

## Changelog：2026-07-17 状态菜单化 v2

**背景**: Round 1 的 cycleStatus (○ ↔ ◐ 单字符循环) 用户嫌"○◐ 状态按钮不好",
信息密度低 + 字符对用户不熟 + 跟 PriorityMenu 下拉风格不一致。

**v2 方案** (commit pending):

- `StatusMenu` 组件 (MainBoard.tsx, 跟 PriorityMenu 同结构)
  - 触发按钮: 色点 + 状态文字 + ⌄ 箭头 (色点 + 文字 双编码, 不用记符号)
  - 下拉 3 行:
    - ○ 未开始 (当前项高亮 accent, 立刻 PATCH status)
    - ◐ 进行中 (当前项高亮 accent, 立刻 PATCH status)
    - ───── (分隔)
    - ✅ 完成 ✨ (弹 4 字段 modal, 不直接切 status)
  - click outside / Esc 关闭, Tab focus + Enter/Space 打开 (基础可达性)
  - 方向键选 / 完整 ARIA role (留 TODO, 跟 PriorityMenu 一起做)

- **删 cycleStatus 函数 + Play "开始" 按钮 + hover ✅ 按钮**
  (三个状态切换入口并入下拉, 视觉去重, 防误触)
- **整行 click 保持** = 完成 modal (muscle memory 保留)
- **完成路径现在只剩 2 个手动入口**:
  - 整行 click → modal
  - 状态下拉 → "完成 ✨" → modal
  - 加上 FocusItem 整行 click + chat LLM 工具, 全部到同一 modal

**为什么不直接 PATCH status="已完成"**:
- 已沉淀的 task 在 storage 层**已被删除** (storage.complete_task 先写 achievement 再删 task)
- 所以"已完成"状态在看板运行时**永远不可达**
- 下拉里放"已完成" 选项会误导用户: 选了之后弹了 modal 不是"切状态"
- 改成显式"完成 ✨" 项, 视觉明确"这一项会弹窗"

**视觉去重决策**:
- Round 1 改造时加了 hover ✅ 完成按钮, 跟整行 click 重复
- v2 直接删, 下拉里"完成 ✨" 是统一入口

## Changelog：2026-07-20 兑现 #1 周报/述职 workspace + 4 项 UX 升级

兑现上次对话（"看一下这个项目然后说一下有什么新想法"）批准的方向：

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **周报/述职 workspace** | `web/app/report/page.tsx` + `web/lib/templates.ts` | 时间范围 × 模板, 左侧升级入口, 右侧 markdown 草稿 + 复制/下载 .md |
| 3 | `cvStatus` 三态 (ready / needs_data / pending) | `app/core/models.py` + CompleteTaskModal + achievements 页 | 述职升级路径中间态, 成就库按状态过滤 |
| 4a | **项目归档 UI** | `web/components/MainBoard.tsx` ProjectCard / ProjectsSection | Archive 按钮 + "已归档 N"开关 + 恢复 |
| 4b | **ChatWindow 重构** | `web/lib/hooks/useChatStream.ts` | 869 → 776 行, 流式状态机抽到独立 hook, 6 个不变量测试锁住 |
| 4c | **`/today` 晨间 ritual** | `web/app/today/page.tsx` | 大日期 + greeting + focus 5 + 完成 button + 已完成折叠 |
| 4d | **AGENTS.md 拆 lessons** | `docs/lessons/{01..04}-*.md` | 275 → 141 行, 按主题分文件, 主页只放索引 |

**回归**：84 → **108** tests pass（+24: cvStatus 模型/存储/API/UI + 3 组新不变量测试锁住 UI 入口）

> Lessons #5-#8 完整内容已迁移到 [`docs/lessons/`](./docs/lessons/README.md), 这里不重复。

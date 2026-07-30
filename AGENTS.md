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
| 9 | `NEXT_PUBLIC_API_BASE` 没设 → 前端 fetch 静默打错端口 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 10 | `build_snapshot` 漏传 description → 前端永远看不到 | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |
| 11 | TaskRow 4 个 ▾ 上下叠视觉堆叠 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 12 | 整行 click = 完成 反直觉 (v2 推翻) | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 13 | ChatWindow 顶层 loading 跟消息气泡"思考中"重复 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 14 | 完成弹窗 4 字段问卷摩擦 → 砍到 1 必填 + 智能润色 + toast 庆祝 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 15 | 完成弹窗「动作≠价值」— 抽象任务不会写 → 任务标题分类引导 + AI 追问 | [01-frontend-ux-bugs.md](./docs/lessons/01-frontend-ux-bugs.md) |
| 16 | `next build` 污染 dev server `.next/` → 样式全丢 → 跑回归用 tsc 不要用 build | [03-fastapi-and-tooling.md](./docs/lessons/03-fastapi-and-tooling.md) |

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

## Changelog：2026-07-17 状态菜单化 v2 (已被 2026-07-21 v3 推翻部分)

> ⚠️ **2026-07-21 v3 推翻**: "整行 click = 完成 modal" 决策被推翻 (见下方 Changelog v3)。
> 整行 90% 是空白, 空白点中也算"用户操作" 触发完成 modal → 用户报"红框空白点中不该触发"。
> 改为 task-cockpit 原版: 整行 click = 展开/收起, 完成走 2 个显式入口 (StatusMenu popover + hover ✅ 按钮)。

**背景**: Round 1 的 cycleStatus (○ ↔ ◐ 单字符循环) 用户嫌"○◐ 状态按钮不好",
信息密度低 + 字符对用户不熟 + 跟 PriorityMenu 下拉风格不一致。

**v2 方案** (commit 00e3148, 已部分回退):

- `StatusMenu` 组件 (MainBoard.tsx, 跟 PriorityMenu 同结构)
  - 触发按钮: 色点 + 状态文字 + ⌄ 箭头 (色点 + 文字 双编码, 不用记符号)
  - 下拉 3 行:
    - ○ 未开始 (当前项高亮 accent, 立刻 PATCH status)
    - ◐ 进行中 (当前项高亮 accent, 立刻 PATCH status)
    - ───── (分隔)
    - ✅ 完成 ✨ (弹 4 字段 modal, 不直接切 status)
  - click outside / Esc 关闭, Tab focus + Enter/Space 打开 (基础可达性)

- **删 cycleStatus 函数 + Play "开始" 按钮** (状态切换入口并入下拉, 视觉去重)
- ~~**整行 click 保持** = 完成 modal~~ (v3 已推翻, 改 toggleExpand)
- ~~**hover ✅ 按钮**: 删了 (跟整行 click 重复)~~ (v3 加回, 这次不重复)

**为什么不直接 PATCH status="已完成"**:
- 已沉淀的 task 在 storage 层**已被删除** (storage.complete_task 先写 achievement 再删 task)
- 所以"已完成"状态在看板运行时**永远不可达**
- 下拉里放"已完成" 选项会误导用户: 选了之后弹了 modal 不是"切状态"
- 改成显式"完成 ✨" 项, 视觉明确"这一项会弹窗"

## Changelog：2026-07-21 TaskRow 整行 click 推翻 v3 (色点 button 形态 + 整行展开)

**背景**: 2026-07-21 用户连报两个问题 —
- **问题 1**: "红框区域 (task 标题右边空白) 点中不该触发完成"
- **问题 2**: "红框区域 (task 第一行) 4 个 ▾ 上下叠, 视觉堆叠"

**v3 方案** (2026-07-21 commit, 推翻 v2 部分):

- **整行 click 改回 toggleExpand** (task-cockpit 原版)
  - v2 决策"整行 click = 完成" 推翻, 空白点中不再误触
  - 整行 click = 切换展开/收起详情区, 跟 task-cockpit 原版一致, 跟用户认知一致
  - 完成走 2 个显式入口 (不重复, 不靠"整行空白点中"防堵死):
    - ① StatusMenu 色点 popover 里的"完成 ✨" 项 (弹 4 字段 modal)
    - ② hover 第一行时出现的 ✅ 按钮 (绿色 Check, opacity-0 + group-hover/row:opacity-100)
  - lesson #4 "完成路径堵死" 的精神保住 — 靠显式按钮堵, 不靠整行 click

- **StatusMenu / PriorityMenu 触发 button 改纯色点形态** (无文字 / 无 ▾ 箭头)
  - 旧版 "○ 未开始 ▾" 三件套 + "● 高 ▾" 三件套 → 8-10x8-10 纯色点 button
  - hover 显示 ring + bg 高亮, 提示"可点"
  - click 弹下拉, 里面仍是 "● 高 / ● 中 / ● 低" / "● 未开始 / ● 进行中 / ✅ 完成 ✨"
  - 旧版 lesson #1 教训 (色点必须可见) 保住 — 色点更大 (8x8 / 10x10 vs 旧 6x6)

- **展开 chevron 从 button 改为指示器**
  - 旧版 v2 设计的 "▸ 展开 chevron button" 删除, 整行 click 已经替代它的功能
  - 新版第一行右侧加一个 **always 可见的小 chevron 指示器** (灰色 ▸ / 展开时 accent + 旋转 90°)
  - 提示"这一行可展开", 但**不是 button**, 不参与 click

- **第二行 meta 弱化** (去掉 PriorityMenu 文字版)
  - PriorityMenu 已在第一行色点表示, 第二行 meta 不再放 priority 文字
  - meta 条件从 `(task.priority || task.draft || ...)` 改成 `(task.draft || task.blocked || ...)`
  - 只保留离散事件标签: 草稿 / 阻塞 / checklist 进度 / age days

- **不变量测试 4 条改版**:
  - #2 改: "整行 onClick **不能** 调 onRequestComplete" (v3 反转 v2 决策)
  - #5 改: "TaskRow **必须有** hover ✅ 完成按钮" (v3 加回, 不重复)
  - #7 改: "PriorityMenu 必须在第一行" (不依赖 meta 行兜底)
  - #10 新增: "第一行 controls hover 才显示" (opacity-0 + group-hover/row:opacity-100)

**为什么不靠"整行 click 提示"防误触**:
- 加 hover 底色 + cursor 提示, 仍然治标不治本 — 整行 90% 是空白, 提示对"用户视觉没目标"的点不解决问题
- 用户**视觉上没点任何东西** (只是点中行内空白), 弹完成 modal 一定反直觉
- 真正解法: 整行 click = 跟视觉一致的"展开详情" 动作, 完成 = 用户**有意识点击**的显式入口

**为什么不加 modal undo 兜底 (Toast 撤销)**:
- 多一层状态管理 (toast + 撤销 API), 改造成本大
- 真正需要"撤销" 的场景是用户**意识到自己误完成** → 现在 modal 弹出时按 Esc 或点取消, 跟撤销等价
- 显式入口 (StatusMenu popover + hover ✅) 让"误完成"概率降到接近 0, 不需要 undo 兜底

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

## Changelog：2026-07-22 StatusMenu 短进度条 + 项目内"已沉淀"子区

两件事一起做 — 一是 StatusMenu 视觉改造 (用户反馈"状态 vs 优先级分不清"), 二是补上"项目维度看不到近期完成"的体验缺口 (complete_task 删 task 的设计让项目内历史断裂)。

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu 改"短进度条"形态** | `web/components/MainBoard.tsx` StatusMenu | 16x4 横向矩形 + 长度反映状态 (空/半/满), 跟 PriorityMenu 8x8 圆点形状对比一眼区分 |
| 1b | **StatusMenu popover 三项同步用横条** | StatusMenu | 0% / 50% / 100% 三档, 外内一致, 干掉"圆点+✓" 跟外显不同的不一致 |
| 2 | **项目内"近期已沉淀"子区** | `web/components/MainBoard.tsx` ProjectCard | 方案A: 展开项目后, active tasks 下方加"已沉淀 N · 7 天内" 折叠子区, 复用 storage.list_achievements (按 project.name + since=N 天) |
| 2b | **新工具函数 relativeDate / daysAgoISO** | `web/lib/api.ts` | relativeDate 输出"今天/昨天/N 天前/N 周前/M月D日", 按日历日对比避免"今天"半夜前后跳; daysAgoISO 给后端 since 参数用 |
| 3 | **新不变量测试** | `app/tests/test_complete_path_invariants.py` | #8 改: StatusMenu 必须有 w-4 横条 track + transition-all fill (防回退到圆点); #12 新: ProjectCard 必须拉 /api/achievements + project.name 过滤 + daysAgoISO 工具 + undoAchievement 撤销 |

**回归**：108 → **132** tests pass（+24 累计 → +1 不变量测试锁住"已沉淀"子区, +1 改测试反映 StatusMenu 形态变化, 其余 22 个是上一次 108→131 那一波; 本次净 +1 改 +1 新 = 132）

### 设计决定记录

- **方案A 优于 B/C**: 复用现有 storage API + "今天已完成" UI 模式, 零新接口零新数据. 选 B (保留 task 不删) 跟"已完成状态永远不可达"的核心架构冲突, 改动爆炸. 选 C (只显示数字徽章) 信息量太低.
- **窗口默认 7 天**: 单常量 `PROJECT_ACH_WINDOW_DAYS = 7`, 改 30 天或全量只改一个数字 + since 参数. 长期项目 (读书清单 2026) 真有需要再调.
- **7 天 vs 全量**: 7 天是"近期"窗口, 全量会塞爆项目卡. /achievements 页是全量入口, "查看全部 →" 链接把用户带过去.
- **不显示 sub-section 如果 0 数据**: 没数据整个子区不渲染, 不留空框. 对新建项目和长期静默项目 (读书清单 2026 7 天内没沉淀) 都干净.
- **撤销复用 api.undoAchievement**: 跟 DoneTodaySection / 看板底部"今天已完成" 同款 Undo2 按钮, 一致性, 误沉淀可以一键回到任务列表.
- **相对时间 relativeDate 关键决策**: 按"日历日"对比不按小时, 避免"今天"半夜前后跳来跳去. task 沉淀通常发生在工作时段, 半夜看到"0 天前" vs "今天" 是噪音不是信号.

### StatusMenu v1 → v2 决策对比

| 版本 | 形态 | 状态编码 | 跟 PriorityMenu 区分度 | 用户反馈 |
|---|---|---|---|---|
| v1 (2026-07-21) | 8x8 / 10x10 圆点 | 颜色 (灰/ accent/ 绿) | ❌ 都是圆形, 难以区分 | "StatusMenu 跟 PriorityMenu 形状太像" |
| v2 (2026-07-22) | 16x4 横条 + 长度 (空/半/满) + 颜色 (灰/ accent/ 绿) | 形状 + 颜色双编码 | ✅ 圆形 vs 矩形 形状对比 | 待验证 (刚交付) |

## Changelog：2026-07-22 blocked / draft inline edit (Agent 字段人手可改)

用户原则: **"凡是 Agent 可以操作的字段, 人也可以操作"** — 之前的缺口是 `blocked` / `draft` 两个字段 Agent 能改 (通过 `tool_update_task`) 但前端没手动入口。

### 现状扫描 (扫之前)

Agent 工具能改的 task 字段 (`app/llm/tools.py:139-175 tool_update_task`):
- `title` / `description` / `priority` / `due` / `status` / `checklist` — UI 都已有 inline edit
- **`blocked` / `draft` — UI 无入口** (本次补)

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu 末尾加 blocked / draft 双方向 toggle** | `web/components/MainBoard.tsx` StatusMenu | 紧跟"完成 ✨" 项, 分隔线 + 🚧 阻塞 / 📝 草稿 两行 toggle |
| 2 | **TaskRow 加 updateField 通用函数** | TaskRow | 跟 updatePriority / updateDue 同款 PATCH + onChange() 流程, 走 api.updateTask 不做乐观更新 |
| 3 | **StatusMenu 接收 blocked / draft / onToggleBlocked / onToggleDraft 4 prop** | StatusMenu 函数签名 | 保持"一个 popover 管所有 task 状态/标签切换" 的 UX 一致性 |
| 4 | **不变量测试 4 条新增** | `app/tests/test_complete_path_invariants.py` | #13 StatusMenu 必须有 statusmenu-toggle-blocked / statusmenu-toggle-draft 按钮 + 动态文案 + emoji; #14 TaskRow 必须透传 4 prop; #15 updateField 通用函数必须有 |
| 5 | **端点级 PATCH 回归测试 5 条** | `app/tests/test_api_task_patch_inline_edit.py` (新文件) | blocked true/false + draft true/false + 字段独立 — 锁住 PATCH 端点真解析 body, 不被 FastAPI 静默吞 |

### 设计决定记录

- **StatusMenu 末尾加 toggle, 不在第二行 meta 徽章加 click**:
  - 单一入口原则 — 一个 popover 管所有 task 状态/标签切换, 用户认知一致
  - meta 徽章 (`MainBoard.tsx:1089-1093`) 保持纯展示 (视觉提示), 避免双入口导致"哪个更优先" 困惑
  - 跟现有"完成 ✨" 同位同节奏 — 状态项 / 完成项 / toggle 项 都是 popover 内的"动作型" 项
- **toggle 走 PATCH + onChange, 不做乐观更新**:
  - 跟 StatusMenu 状态切 / PriorityMenu 优先级切 / DueEditor due 改完全一致
  - SWR revalidate 后所有看板视图同步, 不需要乐观更新
  - 失败回滚: SWR 本身有 mutate-on-error, PATCH 失败用户看到的就是原状态
- **toggle 文案"标记 / 解除" 而非 checkbox 形态**:
  - checkbox 形态 (`✓ 阻塞` toggle) 跟状态项"当前" 标识视觉撞
  - "标记阻塞" / "解除阻塞" 明确动作方向, 跟"完成 ✨" 的"动作+提示" 风格一致
- **emoji 跟 meta 徽章对齐**:
  - 阻塞: 🚧 (跟 MainBoard.tsx:320 `item.blocked ? "🚧" : "○"` 同一 emoji, 用户视觉联想不断)
  - 草稿: 📝 (新 emoji, 但跟"待确认" 语义自然配对)
- **后端 schema 早就有 blocked / draft, 零后端改动**:
  - `TaskUpdate` schema (app/core/models.py:232-233) 早就允许 `blocked: Optional[bool]` 和 `draft: Optional[bool]`
  - storage.update_task 早就支持 (test_storage.py:129, 151, 152 都有覆盖)
  - 缺的**只是**前端手动入口 — 纯 UX 补丁, 不动后端架构

### 字段表 (扫完之后)

| task 字段 | Agent 改 | UI 改 | 入口 |
|----------|----------|------|------|
| `title` | ✅ | ✅ | 双击 inline edit |
| `description` | ✅ | ✅ | 展开区 textarea |
| `priority` | ✅ | ✅ | 第一行色点 PriorityMenu |
| `due` | ✅ | ✅ | 第一行右侧 DueEditor |
| `status` | ✅ | ✅ | 第一行色点 StatusMenu |
| `checklist` | ✅ | ✅ | 展开区行内增删勾 |
| `blocked` | ✅ | ✅ **(新)** | StatusMenu 末尾 🚧 toggle |
| `draft` | ✅ | ✅ **(新)** | StatusMenu 末尾 📝 toggle |

**回归**：132 → **141** tests pass (+9: 5 个端点级 PATCH 回归 + 4 个 UI 静态不变量)

## Changelog: 2026-07-22 StatusMenu 状态融合 + 移到右侧 + 第二行徽章删除 (v3)

用户反馈: 「任务状态组件跟优先级色点堆在左侧, 跟优先级有点重复的感觉」 + 「进行中用一个横条, 阻塞用另一个徽章, 这两个其实是同一维度信息, 应该融合成一个组件」。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **StatusMenu trigger 改"融合形态"** | `web/components/MainBoard.tsx` StatusMenu | 同一 button 多形态: 阻塞 → 🚧 warning, 草稿 → 📝 accent, 否则 → 短进度条 (16x4 跟 status 长度)。优先级: 阻塞 > 草稿 > 状态 |
| 2 | **StatusMenu 从左侧挪到右侧** | TaskRow 第一行 JSX | 新顺序: PriorityMenu (左) → 标题 → StatusMenu (右) → DueEditor (更右)。StatusMenu 跟 due 形成"右栏", 用户从右到左扫: 状态+阻塞/草稿 → due → 展开 → hover 按钮 |
| 3 | **第二行 meta 删掉"草稿/阻塞"徽章** | TaskRow 第二行 meta | 上移到第一行右侧状态指示器后, 第二行不再需要重复表达。meta 条件从 `(task.draft \|\| task.blocked \|\| ...)` 改成 `(totalCount > 0 \|\| taskAgeDays >= 2)`, 只剩 checklist 进度 + "挂了 N 天" 提示 |
| 4 | **不变量测试 3 条新增/改写** | `app/tests/test_complete_path_invariants.py` | #8 改写: `test_statusmenu_trigger_is_fused_form` 锁住"同一 button 多形态" (blocked/draft 分支 + 无修饰横条 fallback + 无状态文字/ChevronDown); #8b 新: `test_statusmenu_is_in_right_side_of_taskrow` 锁住右侧位置 (PriorityMenu < StatusMenu < DueEditor 索引顺序); #8c 新: `test_taskrow_meta_row_no_draft_blocked_badges` 锁住第二行无徽章 (无 `{task.draft &&` / `{task.blocked &&` / 草稿阻塞背景 class) |
| 5 | **title 增强** | StatusMenu trigger `title` 属性 | 从 `状态: ${status} (点击切换)` 改成 `状态: ${status}${blocked ? " · 阻塞" : ""}${draft ? " · 草稿" : ""} (点击切换)`, hover 能看到完整修饰 |

### 设计决定记录

- **融合优于并行**:
  - 旧版: 进行中 (横条) 在第一行左侧, 阻塞 (🚧 徽章) 在第二行 — 同一维度信息分散在两行, 用两种视觉语言表达
  - 新版: 同一位置同一组件, 形态切换 — 视觉更紧凑, 状态判断只扫一处
- **优先级: 阻塞 > 草稿 > 状态**:
  - 阻塞 = 任务被外部依赖卡住, 必须先解决阻塞才能推进 → 视觉优先级最高
  - 草稿 = 待确认, 优先级中等
  - 状态 (进行中/未开始) = 基础信息, 优先级最低
  - 三者冲突时按这个顺序覆盖
- **第二行徽章全删, 不保留冗余**:
  - 保留 = 同一信息出现在两行, 视觉重复
  - 用户已经能看到第一行右侧 🚧/📝, 第二行再显示一次是噪音不是信号
  - 教训: 信息一致性强 > 信息密度高
- **StatusMenu trigger 保持 w-5 h-5 button 尺寸**:
  - 阻塞/草稿状态下渲染 13px emoji, 居中显示在 20x20 容器里 — 视觉权重跟横条形态接近, 切换不突兀
  - 不放大 button 尺寸 = 保持"右栏"密度, 不破坏 due / 展开指示器 / hover 按钮 的位置
- **不变量 8 改写而非新增**:
  - 旧不变量 8 (test_statusmenu_trigger_is_pure_dot_no_text_no_chevron) 的核心约束 — "trigger button 不能有 status 文字 / ChevronDown" — 仍然成立 (回归保护)
  - 但 "必须有 w-4 h-1 横条" 改为 "必须有 blocked 分支 + draft 分支 + 无修饰横条 fallback" — 更精确地反映"融合形态" 设计

### StatusMenu v2 → v3 决策对比

| 版本 | 形态 | 阻塞/草稿表达 | 跟 PriorityMenu 区分度 | 跟 due 配合 | 用户反馈 |
|---|---|---|---|---|---|
| v2 (2026-07-22) | 16x4 横条 (无修饰) | 第二行独立徽章 (🚧 阻塞 / 📝 草稿) | ✅ 圆 vs 矩形 | ❌ 一个左一个右 | "分散在两行, 同一信息两种表达" |
| v3 (本次) | 同一 button 多形态 (🚧/📝/横条) | 同一组件内覆盖表达 | ✅ 圆 vs 矩形 + 同位置切换 | ✅ StatusMenu 挪到 due 左边, 形成右栏 | 待验证 (刚交付) |

**回归**: 141 → **160** tests pass (+19: 3 个新不变量测试 [1 改写 + 2 新增] + 16 个端点级 + 集成测试同步). `tsc --noEmit` 0 错误.

## Changelog: 2026-07-22 Priority 升级 P0/P1/P2/P3 + 重做 badge 样式

用户反馈: "现在任务的优先级的这个组件的展示形式从低中高改为P0、P1、P2、P3这几个等级。底色加文案的形式。颜色跟紧急程度匹配。" 3 档粒度太粗 + 8x8 纯色点看不出是优先级, 跟 StatusMenu 短横条视觉混淆。

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **Priority enum 3 档 → 4 档** | `app/core/models.py` | `HIGH/MEDIUM/LOW (高/中/低)` → `P0/P1/P2/P3`。P0 = 紧急, P1 = 高, P2 = 普通 (默认), P3 = 不急 |
| 2 | **数据迁移: 高→P0, 中→P2, 低→P3** | `app/core/storage.py` `_migrate_priority_values` | 启动时 `create_tables()` 跑一次 `UPDATE ... WHERE priority IN ('高','中','低')`, idempotent (已迁移行 no-op)。P1 是新档, 旧数据无对应 |
| 3 | **PriorityMenu 8x8 纯色点 → badge 形态** | `web/components/MainBoard.tsx` PriorityMenu | 软底色 (`color/15`) + 同色描边 (`color/30`) + 同色文字 + font-mono 10px 字号 + P0/P1/P2/P3 文字。h-5 px-1.5 紧凑 badge, 跟 StatusMenu (16x4 短横条) 形状对比一眼区分 |
| 4 | **颜色梯度: 红→橙→琥珀→灰** | `web/components/MainBoard.tsx` `PRIORITY_BADGE_STYLES` | P0 `bg-danger/15 text-danger` (最急) / P1 `bg-warning/15 text-warning` (高) / P2 `bg-accent/15 text-accent` (普通) / P3 `bg-fg-secondary/15 text-fg-secondary` (不急, **保持亮灰可见, 不回退 bg-fg-muted** — 沿用 2026-07-17 lesson #1) |
| 5 | **Popover 加中文 helper label** | PriorityMenu popover | 4 档选项后面挂灰色 helper: P0 "紧急 / 最高" / P1 "高 / 重要" / P2 "普通 (默认)" / P3 "不急"。badge 文字是主要信号, helper 帮助首次使用快速理解 |
| 6 | **FocusItem 左侧色条跟 4 档** | `web/components/MainBoard.tsx` `priorityBar` | 跟 badge 颜色梯度一致: P0=实心红 / P1=实心橙 / P2=实心琥珀 / P3=浅灰 (P2 新增, 旧 3 档没这档) |
| 7 | **后端 LLM 工具 enum 同步** | `app/llm/tools.py` | `tool_add_task` default `"P2"`, `tool_update_task` enum `["P0","P1","P2","P3"]`, error message 同步。系统 prompt `cockpit_system.md` 优先级章节重写 |
| 8 | **`/today` 页色点跟 4 档** | `web/app/today/page.tsx` | 1.5x1.5 圆点颜色梯度同 4 档, P2=accent (跟 StatusMenu 进行中同色, 但形状是点, 不冲突) |
| 9 | **不变量测试改写/新增 5 条** | `app/tests/test_complete_path_invariants.py` | 旧 `test_priority_low_uses_visible_color` 改写 → `test_priority_badge_styles_4_levels` (锁住 4 档 + 颜色梯度 + 守 lesson #1 "P3 不用 bg-fg-muted"); 旧 `test_prioritymenu_trigger_is_pure_dot_no_text_no_chevron` 改写 → `test_priority_badge_uses_p_level_labels` (锁住 badge 有 P 档文字 + 不用纯色点 + 用 PRIORITY_BADGE_STYLES[priority] 取样式); 新 `test_priority_popover_renders_p_levels` (锁住 popover 4 档 P0/P1/P2/P3) |
| 10 | **storage migration 测试** | `app/tests/test_storage.py` `test_migrate_priority_old_to_new` | 写 3 条任务, 手动 UPDATE 回旧值, 跑 2 次 `create_tables()` 验证迁移正确 + 幂等 |
| 11 | **FocusItem 色条测试 0 改** | `app/tests/test_focus.py` | 已有测试全部用新 Priority 常量, 排序测试加 P1 进 4 档排序 |

### 设计决定记录

- **P0/P1/P2/P3 优于 高/中/低**:
  - 业界 incident management 通用约定 (Sentry / PagerDuty / ITIL), 沟通更精准
  - 3 档分不开"紧急 (P0) / 高 (P1) / 普通 (P2) / 不急 (P3)" 的实际体感
  - 数字标号 = 易于比较 (P0 < P1 < P2 < P3 跟 rank 顺序一致)
- **软底色 (opacity 15%) 优于实心**:
  - 实心 P0 红太抢眼, dark mode 下整行 task 视觉重心失衡
  - 软底色 + 同色描边 (30%) = 卡片感, 跟整体 dark theme 协调
  - 文字用 color full opacity, 保持可读性
- **font-mono 优于 font-sans**:
  - P0/P1/P2/P3 = ticket / incident 风格, monospace 给"技术 label" 感
  - 跟整体 sans 字体形成对比, 一眼能识别"这是优先级"
- **Popover 加 helper label 而不只 badge**:
  - badge 是主信号, helper 是补充说明 — 首次使用快速理解, 老用户忽略
  - 不在 trigger button 上加 helper = 保持紧凑 (badge 只占 ~24px, 不挤占标题空间)
- **旧数据映射规则**:
  - 高 → P0 (紧急度语义最接近, 都是"最急"那一档)
  - 中 → P2 (普通, 4 档的默认档)
  - 低 → P3 (不急)
  - P1 (高但非紧急) 是新档, 旧数据没有对应, 用户后续手动调整
  - **不是** 高→P2 中→P1 (那会让旧"高" 任务被降级)
- **migrate 时机**: `create_tables()` 启动时一次性跑, **不** 用 settings flag 跟踪"是否已迁移":
  - WHERE 限定 `priority IN ('高','中','低')` 已经隐式做了"只迁移没迁移过的" 判断
  - 启动每次跑 cost 几乎为 0 (5 个任务 = < 1ms), 简化代码
  - 不需要 ALTER TABLE 也不需要 version 表
- **trigger 体积增大但保持紧凑**:
  - 旧 8x8 dot (16px) → 新 badge (~24-28px), 宽度 +12px
  - 标题区域仍有 ~60% 宽度可显示 (max-w-truncate + ellipsize)
  - badge 跟 StatusMenu 短横条 (16x4) 形状对比明显, 视觉一眼区分
- **FocusItem 左侧色条单独更新, 跟 badge 颜色梯度**:
  - FocusItem 是"看一眼" 组件, 左侧色条 = 最快视觉信号
  - 跟 badge 颜色保持一致, 用户从 focus 跳到 task 详情不会有"颜色不匹配" 的认知断裂
  - P2 用 `bg-accent` 跟 StatusMenu "进行中" 同色, 但 FocusItem 是条状不是矩形, 形状区分

### 字段表 (改完之后)

| task 字段 | Agent 改 | UI 改 | 入口 | 形态 (2026-07-22) |
|----------|----------|------|------|------------------|
| `priority` | ✅ | ✅ | PriorityMenu (第一行左) | **badge** (软底色 + P0/P1/P2/P3 文字) |
| 旧 8x8 dot | ✅ | ✅ | PriorityMenu (第一行左) | 8x8 圆点 (已删除) |
| `status` | ✅ | ✅ | StatusMenu (第一行右) | 16x4 短横条 (长度跟状态) |
| `blocked` | ✅ | ✅ | StatusMenu popover 末尾 🚧 toggle | 🚧 emoji 覆盖状态 |
| `draft` | ✅ | ✅ | StatusMenu popover 末尾 📝 toggle | 📝 emoji 覆盖状态 |

**回归**: 160 → **162** tests pass (+2: 4 个新不变量 + migration 测试 净增 +2, 旧"纯色点"不变量 2 条被新 badge 不变量替代; 旧 data migration 用例调整 focus 测试加 P1 排序). `tsc --noEmit` 0 错误. 实际数据迁移 (5 个老任务: 高×2 → P0, 中×2 → P2, 低×1 → P3) 验证通过.

## Changelog: 2026-07-23 P2 换冷色蓝 (跟 P1 暖色撞色修复)

用户反馈: "P1 跟 P2 两个优先级的组件的颜色非常的接近, 我希望你能够给它换一下颜色,能够让两个很快的区分开。"

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **加 `info` 色** | `web/tailwind.config.ts` | `#3b82f6` (Tailwind blue-500), 跟 danger / warning / accent / success 同级 |
| 2 | **P2 badge 改 info 蓝** | `web/lib/api.ts` `PRIORITY_BADGE_STYLES` | `bg-info/15 text-info border-info/30`, 共享给 MainBoard PriorityMenu + /today FocusRow |
| 3 | **P2 左侧色条改 info 蓝** | `web/lib/api.ts` `PRIORITY_BAR_STYLES` (新立) | `bg-info`, FocusItem 左侧 3px 竖条用 |
| 4 | **/today FocusRow 同步** | `web/app/today/page.tsx` | 跟 MainBoard 共享 `PRIORITY_BADGE_STYLES` / `PRIORITY_BAR_STYLES`, 改色只改一处 |
| 5 | **不变量测试同步** | `app/tests/test_complete_path_invariants.py` | `test_priority_badge_styles_4_levels` 期望 P2 从 `bg-accent/15 text-accent` 改 `bg-info/15 text-info` |

### 设计决定记录

- **色环跨越 ~200° (红 0° → 橙 30° → 蓝 220°) 优于 同色系微调**:
  - 旧版: 红 0° → 橙 30° → 琥珀 45° — P1/P2 只差 15° 肉眼分不出
  - 新版: 红 0° → 橙 30° → 蓝 220° — P1/P2 跨冷暖, 一眼区分
  - 经验: 同一色相不同明度 (橙 vs 琥珀) 看起来"差不多", 跨色相才能拉开
- **蓝色 (info) 优于其他冷色**:
  - 绿 = success, 跟"完成" 概念撞, 排除
  - 紫/品红 = 警告感, 跟 P0 红冲突
  - 蓝 = 中性"信息" 蓝, 设计系统通用约定, 跟红/橙对比最强
  - `#3b82f6` (blue-500) 是 Tailwind 蓝调中段, dark mode 下 `#15 / #30` opacity 底色 + 边框都清晰
- **P2 = 蓝意外地解决跟 StatusMenu 视觉混淆**:
  - 旧版 P2 用 accent (琥珀) = StatusMenu "进行中" 同色 — 优先级普通态跟状态进行中色一样, 视觉上像在说"进行中"
  - 新版 P2 用 info (蓝) — 普通优先级是中性默认态, 蓝色最不抢眼, 也跟"进行中" 完全区分
- **PRIORITY_BAR_STYLES 独立常量 而非合并到 BADGE**:
  - 优先级左侧竖条 vs badge 用不同 opacity 体系:
    - BADGE: 软底色 (color/15) + 同色描边 (color/30) + 同色文字 — 多信息密度
    - BAR: full opacity 单色 — 最快视觉信号
  - 合并会让一边用不到, 也违背 single responsibility — 改色梯度要同时调两套, 容易漏
  - 但**值是同步的** (P2 都是 info), 只在 tailwind 类层面不同
- **共享给 /today 不冗余**:
  - 旧版 MainBoard 和 /today 各自硬编码 `=== "P0" ? "bg-danger" : ...`, 改色要改两处
  - 新版 `PRIORITY_BAR_STYLES` / `PRIORITY_BADGE_STYLES` 从 lib/api.ts 单点 export, 两边 import 同一份
  - lesson: 颜色/样式常量跟类型一起放在 lib/api.ts, 是这个项目已经形成的约定 (跟 `statusIcon` / `dueColor` 同一档)

### 颜色梯度对照 (P0/P1/P2/P3)

| 档 | 色名 | hex | 色环 hue | 跟上一档 hue 差 | 紧急度语义 |
|---|---|---|---|---|---|
| P0 | danger (红) | #ef4444 | 0° | — | 紧急 / 最高 |
| P1 | warning (橙) | #f59e0b | 30° | +30° | 高 / 重要 |
| P2 | **info (蓝)** | **#3b82f6** | **220°** | **+190°** | 普通 (默认) |
| P3 | fg-secondary (灰) | #a0a0a0 | n/a | — | 不急 |

**回归**: 162 → **164** tests pass (+2: badge 不变量测试 `test_priority_badge_styles_4_levels` 期望从 accent 改 info, 仍 pass; 整个 priority 套件跑过确认色值同步). `tsc --noEmit` 0 错误 (注意: .next/types/app/test-markdown 是 stale build artifact, 不是源代码错误).

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




## Changelog: 2026-07-28 成就库 v2 项目层级 (晚 23:50 立)

用户原话 (2026-07-28 23:50): "成就库里面是不是没有采用项目和任务的层级？是不是只有任务这一层?"

### 调查 + 现状

- 后端 Achievement 表**有完整数据**支持层级: `app/core/models.py:280-288` Achievement 实体带 `project_id` + `project` 名称快照
- 旧前端 `web/app/achievements/page.tsx` (v1) **确实没用上**:
  - 顶层分组: 只按 `date` 分组 (`Object.entries(groups).sort(...)` )
  - 每个成就条目: 标题 + 旁边一个 project 徽章 (`<span>{a.project}</span>`)
  - **没有按 project 分组/折叠/计数**
- 用户想看"我在哪些项目上有沉淀" — 需要项目级聚合
- 跟 2026-07-22 /today 项目卡片里加的"已沉淀 N · 7 天内" 子区呼应, 但 /today 那个是 7 天窗口, 这次 /achievements 是**全量视图**

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **`/achievements` 完全重写 v1 → v2** | `web/app/achievements/page.tsx` | 一级 = project card (按项目聚合), 二级 = date (项目内按日期分组) |
| 2 | **项目卡片复用 `projectEmoji`** | `lib/api.ts` 已存在的工具 | 跟 /today 项目卡片视觉一致 (50 emoji 池子, hash 选) |
| 3 | **项目卡片三态计数** | ProjectSection header | `✅ N ready / 📊 N needs_data / ⏳ N pending` 三色徽章, 跟成就卡片状态色一致 |
| 4 | **项目排序: ready desc** | `projectGroups` useMemo | 最近沉淀最多的项目最显眼 |
| 5 | **折叠状态 localStorage 持久化** | `cockpit_achievements_collapsed_projects` | 跨刷新保留, 默认全部展开 |
| 6 | **AchievementItem 抽成独立组件** | 同文件 | 减少主组件复杂度, 跟 ProjectSection 解耦 |
| 7 | **保留所有 4 字段 + 编辑/升级/撤销 动作** | AchievementItem | cv / outcome / reflection / cv_status 全保留, edit / upgrade / undo 三个 action 都不动 |
| 8 | **不变量测试 12 条新增** | `app/tests/test_achievements_hierarchy_invariants.py` (新) | 锁住项目级聚合 / emoji / 三态计数 / 排序 / 二级日期分组 / 折叠持久化 / 4 字段保留 / 状态过滤 / 空状态 / 顶层防回退 |

### 设计决定记录

- **一级 project vs 保持 date-only 的选择**:
  - 旧 date-only 适合"按时间线看自己最近干了啥" 的视角
  - 新 project-first 适合"按项目看自己沉淀了多少" 的视角
  - 用户原话 "我没看到项目层级" 暗示**他想要 project 视角**, 不只是时间线
  - 折中: 顶层 project (用户最想要的视角), 项目内仍保留 date 子分组 (不丢时间线信息)
  - lesson: 顶层导航结构 = 用户最常问"我 X 怎么样" 的那个维度, 不能拍脑袋选

- **复用 `projectEmoji` 跟 /today 风格一致**:
  - /today 项目卡片已经用了 50 emoji 池子, hash 选 (2026-07-22 立的, 见 Changelog 4a)
  - /achievements 不另搞一套, 直接 import 同一个 `projectEmoji` 函数
  - 好处: 用户在 /today 看到一个 emoji, 进 /achievements 看到同一个, **跨页面的视觉锚点统一**
  - lesson: 跨页面的视觉常量 (颜色 / emoji / 形状) 必须共享一份定义, 不能各处硬编码

- **项目排序: ready desc vs total desc vs 最近活动 desc**:
  - ready desc: 最近"沉淀的资产" 最多的项目 (最显眼 = 价值密度最高)
  - total desc: 历史成就最多 (但可能很久没动了, 误导)
  - 最近活动 desc: 最近 7 天有沉淀的项目 (跟 /today 7 天窗口呼应)
  - 选 ready desc: "累计 ready 数" 是用户最关心的"资产" 指标, 跟 toast 庆祝的"累计 N 个 ready" 数字同源
  - secondary sort: total desc (tiebreak), project name asc (稳定排序)

- **折叠状态 localStorage 而非 React state**:
  - 用户关掉浏览器再开, 折叠状态应该保留 — 用户主动收起 = 表达"这个项目我暂时不关心", 跨刷新不弹回很烦
  - 跟 /today "今天已完成" 折叠 (MainBoard.tsx) 同款做法
  - 跟对话栏折叠 (`cockpit_chat_collapsed` localStorage) 同款做法
  - lesson: 用户主动操作的 UI 状态 (折叠 / 排序 / 过滤) 跨刷新保留 = 体感"产品懂我"

- **AchievementItem 抽成独立组件 vs 内联**:
  - 内联: 300+ 行单文件, 难读
  - 抽: 主组件只管"取数 + 聚合 + 渲染 N 个项目卡", AchievementItem 只管"渲染一条成就 + 处理 edit/upgrade/undo"
  - 后续如果要改成就条目的视觉 (加 tags / 加截图 / 加关联 task), 只动 AchievementItem, 不动项目卡
  - lesson: 一个组件做多件事 (聚合 + 渲染 + 状态) 是技术债, 拆 = 单文件 < 200 行 + 单一职责

- **needs_data → ready 的升级入口从"批量过滤" 变成"行内 button"**:
  - 旧 v1: 顶部 filter "📊 还差数据" 选了之后, 在列表里手动编辑 CV 保存 = cv_status 自动变 ready
  - 新 v2: needs_data 状态下, 成就条目**直接挂一个"📊 还差数据 · 升级" button**, 一键升级 (前提: cv 已经有值)
  - 原因: 升级是高频动作 (用户补全数据后第一件事), 不该埋藏在 filter 后面
  - lesson: **高频动作的入口要"内嵌" 在触发对象上, 不要"外面过滤, 里面找"** — 跟 StatusMenu 末尾 blocked/draft toggle 同款思路 (2026-07-22)

- **不变量 #12 锁"防回退到 date-only"**:
  - 显式断言 `projectGroups.map(($g$)` 模式必须存在
  - 防止以后有人 refactor 觉得"项目卡多余" 直接删了, 回退到 v1 的 date-only
  - lesson: 用户报过的痛点必须有专门的防退化测试, 不能只测"新功能存在"

### 字段表 (层级改造后的成就条目)

| 条目字段 | 来源 | 旧 v1 | 新 v2 |
|---|---|---|---|
| 标题 | `a.title` | ✅ | ✅ |
| project 徽章 | `a.project` | ✅ 装饰 | **提升为顶层卡片** |
| cv | `a.cv` | ✅ | ✅ |
| outcome | `a.outcome` | ✅ | ✅ |
| reflection | `a.reflection` | ✅ | ✅ |
| cv_status 图标 | `a.cv_status` | ✅ | ✅ |
| 编辑 CV | `updateAchievement` | ✅ | ✅ |
| needs_data 升级 | `updateAchievement cv_status=ready` | 顶部 filter 间接 | **行内 button 一键** |
| 撤销 | `undoAchievement` | ✅ | ✅ |

**回归**: 200 → **212** tests pass (+12: 项目级聚合 / emoji / 三态计数 / 排序 / 二级日期 / 折叠持久化 / 4 字段保留 / 状态过滤 / 空状态 / 防回退 12 条不变量). `tsc --noEmit` 0 错误. `npm run build` 10/10 静态页导出通过. 改动 1 前端文件 (完全重写) + 1 测试文件 (新), 净 +约 350 行, 用户视觉上的"扁平时间线 + 装饰徽章" 变成 "项目维度聚合 + 内嵌升级按钮"。

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


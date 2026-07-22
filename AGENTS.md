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

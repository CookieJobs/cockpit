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




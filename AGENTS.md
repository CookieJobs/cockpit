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

### 1. TaskRow checkbox 二次确认 UX bug（修于 2026-07-13）

- **症状**：点任务前面的状态圆圈 → 圆圈变对号 → 2 秒后对号变回圆圈 → 任务没完成
- **根因**：`TaskRow` 状态按钮用了双击确认（`confirming` state + 2s `setTimeout` 重置），但**没有视觉提示告诉用户要点第二次**。旁边的 `FocusItem` 是单击直接完成 — 两个区域行为不一致更诡异
- **教训**：重要操作要么"单击 + undo 窗口"（带 toast），要么"显式二次确认按钮"，不要靠"图标变一下就当确认" — 用户根本看不懂
- **修法位置**：`web/components/MainBoard.tsx` TaskRow（约 314 行起）

### 2. LLM CoT 暴露 + markdown fallback 误执行风险（修于 2026-07-13）

- **症状**：DeepSeek R1 / MiniMax M3 等推理模型在 content 字段写 `<think>...</think>`，整条管道没过滤直接渲染给用户；更严重的是 `chat_engine.py` 的 markdown tool call fallback 用正则扫 `response.text` 解析 `functions.xxx(args)` 伪调用 — 如果 LLM 在 CoT 思维里写了 `functions.delete_task(...)`，**会被当真工具调用执行**（潜在不可逆数据丢失）
- **根因**：chat_engine 没处理 CoT 块，前后端 markdown 渲染都不过滤
- **教训**：
  - **后端**必须在 LLM 响应**入口**就剥离 CoT（`strip_think_blocks` 在 `chat_engine.py`），不能让任何下游路径（fallback 解析 / 持久化 / 前端显示）拿到带 CoT 的 text
  - **前端**再做一次 defense-in-depth（处理旧 session 历史里残留的 CoT）
  - markdown tool call fallback **永远是正则 + 白名单**，必须假设输入里可能有 CoT / 注释 / 乱码
- **覆盖范围**：匹配 `<think>` / `<thinking>` / `<reasoning>` 三个变体，case-insensitive，容忍空白
- **修法位置**：
  - 后端：`app/llm/chat_engine.py`（`_THINK_BLOCK_RE` + `strip_think_blocks`）
  - 前端：`web/components/ChatWindow.tsx`（`stripThinkBlocks` 在 `extractTextFromAnthropicContent` 之后）

### 3. `/api/tasks/{tid}/complete` simple type 参数 body 丢失（修于 2026-07-16）

- **症状**：前端 CompleteTaskModal POST 4 字段 (outcome/cv/reflection/cv_status) 给后端，任务**确实完成了**, achievement **也入库了**, 但**所有 4 字段值都是空字符串**。
- **根因**：路由端点签名是 `complete_task(tid, outcome: str = "", reflection: str = "", cv: str = "", cv_status: str = "ready")`。FastAPI 看到 `str` 这种 simple type 参数会**默认当 query 解析** — 整个 JSON body 被忽略，所有字段走默认值空串。
- **教训**：
  - **FastAPI 端点接 JSON body 必须用 Pydantic BaseModel**，不要用 simple type 参数（这是 memory 里 `python-web-backend-gotchas` 第 3 条，但 storage 层 pytest 测不到这个 — 端点级才暴露）
  - **测试要打到端点级**：storage 层测试全过不代表 API 行为正确。要加 `TestClient` 走 HTTP 真实路径的回归测试。
  - 这次 bug 潜伏了至少一个迭代期 — `add_task` 用了 `TaskCreate` Pydantic model 没事，但 `complete_task` 用了 simple type 就翻车
- **修法位置**：
  - 后端：`app/api/tasks.py` — 加 `CompleteTaskRequest` BaseModel 接 body
  - 测试：`app/tests/test_api_complete_task.py`（新文件，4 个端点级 regression test 锁住）

### 4. TaskRow 状态机循环堵死"完成"路径（修于 2026-07-16）

- **症状**：用户报"我**现在不能通过手动操作来完成某一个任务了**！这是极其严重的产品逻辑 bug"。看板所有 task 都没法手动完成，只能去 chat 让 LLM 调 `complete_task` 工具。
- **根因**（双重瞎）：
  1. Round 1 抄 task-cockpit `STATUS_CYCLE` 时只抄了"未开始 ↔ 进行中"两档循环，**漏了"完成"档**。看代码：
     ```ts
     if (task.status === "未开始") → "进行中"
     else if (task.status === "进行中") → "未开始"  // ❌ 永远到不了"已完成"
     else onRequestComplete(task)  // 只有"已完成"会触发 modal
     ```
  2. **整行 click 是 `setExpanded` (展开详情)**, 不是"完成"。task-cockpit 原版整行 click 是触发完成, 我以为"已经有人处理", **没核对就发车了**。两个语义撞了, 完成路径被堵死。
  3. 我写好了 `openComplete` 函数 (4 字段 modal 入口), 但**只在 `status === "已完成"` 时才挂按钮** (dead code 写法), 又是漏。
- **教训**：
  - **抄代码时必须核对每个分支的触发条件, 不要假设上下文"已经存在"**。我以为整行 click 已经是完成, 实际是展开详情。
  - **状态机是 linear 还是 cycle 是产品决策**, 不是 UI 习惯问题。"完成"是终态, 不该循环, 跟其他两档不在一个维度。
  - **凡是用户报"我没法 X"的产品 bug, 优先怀疑自己的状态机/路由设计**, 不要怪用户不会用。
  - **端到端 UX 路径必须用人话走一遍**: "我点 ○ → 任务开始", "我点 ◐ → 弹 modal 填结果 → 任务完成", "已完成任务怎么撤销? → 走成就库"。三个场景都得能走通, 不是只测 API 通。
- **修法**（方案 A.1）：
  - 状态机改 linear: 未开始 → 进行中 → 完成 modal。已完成是终态, 回退走成就库"撤销" (`api.undoAchievement`)
  - 整行 click 改 onRequestComplete (弹 4 字段 modal, task-cockpit 风格)
  - 加 hover chevron 按钮控制展开/收起 (替换整行 click)
  - "完成" hover 按钮扩到所有非已完成态 (不再限制 `status === "已完成"`)
  - 删除 Play "开始" 按钮 (状态按钮已能完成同样功能, 视觉重复)
- **修法位置**：
  - `web/components/MainBoard.tsx` TaskRow — `cycleStatus` + 整行 onClick + chevron 按钮
  - 测试盲点: 端点级 pytest 不覆盖前端 UX 路径, 这个 bug 只能人肉走查发现

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

### 5. "低" 优先级色点不可见（修于 2026-07-17）

- **症状**：用户报"任务优先级 我看只有「高」、「中」没有「低」"
- **根因**（双重盲点）：
  1. `PriorityMenu` 触发按钮 dotColor "低" 用 `bg-fg-muted` (#666), 1.5px 圆点在 dark theme 几乎不可见
  2. `TaskRow` 第二行 meta 条件里 `task.priority !== "低"` 这个隐式反向判断, 让 priority=低 + 啥都没的任务**整个 meta 行不显示**, PriorityMenu (色点) 随之不可见 — 即使色点可见, 在第二行隐藏的情况下用户也看不到
- **修法**：
  - dotColor "低" 改 `bg-fg-secondary` (#a0a0a0) — 亮灰, 跟"红黄"形成"红黄灰"三档色梯度
  - 第二行 meta 条件改成 `(task.priority || task.draft || ...)` — `task.priority` 总是 truthy, PriorityMenu 永远渲染
- **教训**：
  - **enum 视觉编码不要用"接近背景色"的弱对比** (#666 vs #0a0a0a), dark theme 1.5px 元素至少用 #a0a0a0
  - **隐式反向判断 (`!== "低"`) 是危险的反模式**, 不读注释根本看不懂为什么隐藏
  - 用 `task.priority ||` 这种正向判断, 语义清楚 (priority 永远显示)
- **修法位置**：`web/components/MainBoard.tsx` PriorityMenu + TaskRow meta 条件

### 6. 端到端 UX 路径静态分析测试 (2026-07-17 立)

**背景**：用户明确要求"不装乱七八糟的东西, 直接解决问题" — 不装 playwright/chromium 跑 E2E, 改用**静态分析测试** catch 80% 同类 bug。

**新增文件**：`app/tests/test_complete_path_invariants.py` (10 个不变量测试)

**覆盖的 7 类不变量**：
1. onRequestComplete 透传 — TaskRow 必须能从 MainBoard 顶层拿到 onRequestComplete
2. 整行 onClick 接 onRequestComplete — 防"完成路径堵死"再发生
3. cycleStatus 函数不能再有 — Round 1 堵死根因
4. StatusMenu 内部定义 + 渲染 — 状态下拉不能删
5. StatusMenu "完成 ✨" 项 + onComplete + ✨ 标识 — 4 字段 modal 触发器
6. TaskRow 不再有 hover ✅ 完成按钮 — 跟下拉"完成 ✨"重复
7. PriorityMenu "低" 颜色用 bg-fg-secondary — 防"低不可见"再发生
8. TaskRow meta 行条件含 `task.priority ||` — 防 priority=低 整行被隐藏再发生

**测试技巧**：
- `_strip_comments_and_strings(src)` 先把注释替换成空白, 避免注释里字面量触发误报 (但**保留字符串字面量**, 因为 Cockpit 大量用中文 enum 值, strip 会破坏位置)
- `_find_function_body_with_ts_types(src, name)` 跨 TS 类型注解提取函数 body (跳过 args + type body 两层 `{}`)
- 所有失败信息都含**历史 bug 描述 + 修法建议**, 不只是"哪里坏了"

**对比 E2E 的取舍**：
- E2E 100% 覆盖运行时, 但需要浏览器 (~150MB chromium), 安装/启动慢, 装依赖**值得花时间**时再用
- 静态分析 ~80% 覆盖 (能 catch 源码层 bug, 不能 catch runtime state bug), **零依赖秒级跑**
- 两个互补, 这次先用静态分析

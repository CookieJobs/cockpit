# 01 — 前端 UX 状态机 / 视觉编码 Lessons

> 三条都跟 TaskRow 状态机 / 视觉编码相关。前端 UX 是 Cockpit 的护城河, 这块的 bug 用户会直接报。

## #1. TaskRow checkbox 二次确认 UX bug（修于 2026-07-13）

- **症状**：点任务前面的状态圆圈 → 圆圈变对号 → 2 秒后对号变回圆圈 → 任务没完成
- **根因**：`TaskRow` 状态按钮用了双击确认（`confirming` state + 2s `setTimeout` 重置），但**没有视觉提示告诉用户要点第二次**。旁边的 `FocusItem` 是单击直接完成 — 两个区域行为不一致更诡异
- **教训**：重要操作要么"单击 + undo 窗口"（带 toast），要么"显式二次确认按钮"，不要靠"图标变一下就当确认" — 用户根本看不懂
- **修法位置**：`web/components/MainBoard.tsx` TaskRow（约 314 行起）

## #4. TaskRow 状态机循环堵死"完成"路径（修于 2026-07-16）

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

## #5. "低" 优先级色点不可见（修于 2026-07-17）

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

## #11. TaskRow 第一行 + 第二行 4 个 ▾ 上下叠，视觉堆叠 (修于 2026-07-21)

- **症状**：用户报"红框区域非常乱, 希望重构一下"。截图：AI度项目展开下，task「抖音2.0」第一行是"○ 未开始 ▾" 状态下拉，紧接第二行是"● 高 ▾" 优先级下拉，**两个下拉箭头垂直距离不到 30px**，加上 due 编辑器自己的 popover 和展开 chevron hover 出现，一个 task 行 4 个 ▾ 箭头挤一起，色点 + 文字 + 箭头视觉堆叠。
- **根因**（设计选择没跟上"信息密度"）:
  - 旧版 StatusMenu 是 "○ 未开始 ▾" 三件套（单字符 + 文字 + 下拉箭头），PriorityMenu 是 "● 高 ▾"（色点 + 文字 + 下拉箭头）— 两个 menu 都同时塞了 **3 个视觉元素**
  - StatusMenu / PriorityMenu 各自占独立 flex 项，StatusMenu 在第一行、PriorityMenu 在第二行 meta 区，**两个 ▾ 箭头垂直方向距离 = 一个 task 行高 (24-32px)**，眼睛扫到会以为是一个下拉的两个分组
  - lesson #1 教训是"色点 + 文字双编码为了可见性" — 我把"双编码"理解成"必须同时显示色点 + 文字"，结果**冗余编码 + 冗余箭头** = 视觉堆叠
- **修法**（3 文件 + 1 测试更新 + 3 新不变量）:
  1. **StatusMenu / PriorityMenu 触发 button 改成纯色点 button 形态**：
     - 10x10 (status) / 8x8 (priority) 圆点，居中放在 20x20 button 内
     - 不显示 status 文字 (未开始/进行中) — 改用 title tooltip + 状态色点颜色区分（灰/accent/绿）
     - 不显示 priority 文字 (高/中/低) — 改用 title tooltip + 色点颜色（红/黄/亮灰，亮灰 lesson #1 教训保住）
     - 不显示 ▾ ChevronDown — 触发 button 自身就是 button，popover 是下拉结果不是常态控件
     - hover 时显示 ring + bg 高亮，暗示"可点"
  2. **TaskRow 第一行重排**：
     - 左边：`[StatusMenu 色点] [PriorityMenu 色点] [标题 flex-1] [due 标签] [▸ 展开 hover] [🗑 删除 hover]`
     - 展开 chevron 和删除按钮 opacity-0 默认隐藏，hover 第一行才出现（`group-hover/row:opacity-100`）
     - 完成入口保持 2 个：整行 click（最显眼）+ StatusMenu popover 里"完成 ✨"（最显式）。不引入第三个 hover ✅ 按钮（违背 v2 决策）
  3. **TaskRow 第二行 meta 弱化**：
     - meta 条件去掉 `task.priority ||`（PriorityMenu 已经在第一行）
     - meta 只显示离散事件标签：草稿 / 阻塞 / checklist 进度 / age days
     - lesson #1 "PriorityMenu 永远可见" 的目标保持（色点在第一行），但实现路径从"靠 meta 行兜底" 改成"在第一行独立" — 更直接
  4. **不变量测试**（`test_complete_path_invariants.py` 加 4 条新不变量）:
     - #7 改版：PriorityMenu 必须在第一行（不依赖 meta 行渲染）
     - #8 新增：StatusMenu 触发 button 不能含状态文字 / ChevronDown，必须含 w-2.x rounded-full 色点
     - #9 新增：PriorityMenu 触发 button 同上
     - #10 新增：TaskRow 第一行 controls 必须 hover 才显示（opacity-0 + group-hover/row:opacity-100）
- **教训**：
  - **"双编码为了可见" ≠ "必须同时显示所有编码维度"** — 旧版色点 + 文字 + ▾ 三个维度同框，反而把冗余编码做成视觉堆叠。色点 + 文字可选 hover 时显示一个比同框更干净
  - **"色点 + 文字双编码"教训要严格区分信息 vs 控件** — lesson #1 的目标是 "色点要可见"，不是 "必须一直显示文字"。重构后色点永远是 button，文字只在 popover 里出现，可见性保住，视觉不堆
  - **每加一个菜单组件都要想"它跟现有 menu 的垂直距离是多少"** — TaskRow 第一行 + 第二行 32px 间距放两个 ▾ 是设计错误。色点编码 + 同一行布局是天然解
  - **状态信息可以分两层**：色点（永远可见）提供"我现在是啥态"，文字（popover 选单）提供"我要选啥"。两层各司其职，不是必须同框
  - **"加 hover ✅ 完成按钮"诱惑要忍住** — 看到"色点 + 标题" 第一行很单调会想加按钮，但**3 个完成入口 (整行 click + StatusMenu + hover ✅) 比 2 个 (整行 + StatusMenu) 误触风险高一倍**。v2 决策正确
- **修法位置**：
  - `web/components/MainBoard.tsx` StatusMenu / PriorityMenu 触发 button 形态重写 + TaskRow 第一行重排
  - `app/tests/test_complete_path_invariants.py` #7 改版 + #8/#9/#10 新增

## #12. 整行 click = 完成 反直觉（推翻 v2 决策, 2026-07-21）

- **症状**：用户报"红框区域 (task 标题右边空白) 点中会触发「完成任务」流程, 这不应该"。截图：AI度项目下「抖音2.0」task 标题右边的大片空白点中 → 弹完成 modal。
- **根因**（v2 决策的副作用）:
  - 2026-07-17 v2 决策: "整行 click = 完成 modal", 解决 lesson #4 "完成路径堵死"
  - 代价: 整行 90% 是空白, **空白点中也算"用户操作"** → 弹完成 modal
  - 用户视觉上"什么都没点中" (没点中标题文字、没点中色点、没点中 due/chevron/删除), 只是点中行内空白, 却被弹了完成 modal
  - lesson #4 真正的教训是"完成路径不能堵死" — 但**不需要靠"整行 click"防堵死**, 靠显式按钮也能防
- **修法（v3 决策, 2026-07-21 commit）**:
  - **整行 click 改回 toggleExpand** (task-cockpit 原版)
    - 整行 click = 切换展开/收起详情区, 跟 task-cockpit 原版一致, 跟用户认知一致
    - 空白点中 = 展开/收起, 视觉一致, 不反直觉
  - **完成走 2 个显式入口 (不重复)**:
    - ① StatusMenu 色点 popover 里的"完成 ✨" 项 (弹 4 字段 modal)
    - ② hover 第一行时出现的 ✅ 按钮 (绿色 Check icon, opacity-0 + group-hover/row:opacity-100)
  - **展开 chevron 从 button 改为指示器** (always 可见的小 ▸, 不是 button)
  - 不变量测试 #2/#5 改版:
    - #2: 整行 onClick **不能** 调 onRequestComplete (v3 反转 v2)
    - #5: TaskRow **必须有** hover ✅ 完成按钮 (v3 加回, 不重复)
- **教训**:
  - **"防堵死" 不一定靠"加大 click 区域"** — 整行 click 看起来"易触发" = 防堵死, 但 90% 空白点中 = 误触。**防堵死的正确方式是"显式按钮 + 强视觉提示"** (hover 出现的 ✅ 按钮 + StatusMenu popover), 让用户**有意识点击**
  - **"视觉一致" > "易触发"**: 整行 = 展开 (视觉一致) 比 整行 = 完成 (易触发但反直觉) 更优。功能可达性靠 hover 按钮 + popover, 不靠整行 click
  - **"完成" 是低频显式动作, 不是高频轻量操作** (跟 AGENTS.md 设计哲学的"对话驱动 vs 看板 inline edit 边界" 一致 — 完成是 LLM 上下文相关的, 应该弹 4 字段 modal 让用户走心, 不是点空白就走流程)
  - **设计 trade-off 要有可回退的窗口**: v2 决策锁了 5 天 (07-17 → 07-21), 没出现"误触" 报告是因为用户刚好点中标题/色点的频率高。这次 user feedback 才暴露"空白点中"问题。**v3 推翻 v2 不是"v2 错了", 是"v2 经验上够用但被新信息推翻"** — 接受推翻, 不维护面子
  - **不变量测试要随设计决策翻转**: #2 测试 v2 锁住"整行必须调 onRequestComplete", v3 改成"整行不能调 onRequestComplete"。**测试是设计决策的化石**, 翻设计要同步翻测试
- **修法位置**：
  - `web/components/MainBoard.tsx` TaskRow 第一行 onClick (toggleExpand) + 展开 chevron 改指示器 + hover ✅ 按钮加回
  - `app/tests/test_complete_path_invariants.py` #2 改版 (反转) + #5 改版 (加回 hover ✅)
  - `AGENTS.md` Changelog 加 v3 段 (推翻 v2 部分)

## #13. ChatWindow 顶层 loading 框跟消息气泡内"思考中…"重复，视觉堆叠 (修于 2026-07-23)

- **症状**：用户报"发完消息之后，红框区域里总是有两个『思考中...』堆在一起"。截图：对话框最下方红框里上下叠着两个一模一样的"思考中..." indicator, 一个带 sparkle icon, 一个是纯文本。
- **根因**（跟 #11 同源 — "视觉堆叠"）:
  - **两处独立的"思考中"渲染**:
    1. **顶层 `loading` 指示器**（`web/components/ChatWindow.tsx` 旧 line 485-494）：只要 `loading=true` 就渲染
    2. **消息气泡内 EventsView**（`web/components/ChatWindow.tsx` line 739-744）：当 `streaming && events.length === 0` 时也渲染
  - **时序必然撞**: `useChatStream` 里 `setMessages([..., userMsg, agentMsg])` (line 69) 之后立即 `setLoading(true)` (line 70), 同步执行
    - 所以 `loading=true` ⟺ "messages 里有 streaming agent message" **永远**同时为真
    - 顶层 loading 框 跟 消息气泡内的 "思考中…" 永远一起出现 = 视觉堆叠
  - **历史原因**（不是设计错误，是 refactor 副作用）:
    - 2026-07-09 最早版 ChatWindow：只有顶层 loading 框（line 485-494 那块）
    - 2026-07-20 重构抽 useChatStream hook：新增 EventsView，EventsView 处理 stub message（`events=[] + streaming=true`）时也加"思考中…" fallback
    - 两者并存 = 必然重复，但一直没人发现
- **修法**（1 处删除 + 2 条新不变量）:
  1. **删掉 ChatWindow 顶层 `{loading && <思考中...>}` 块**（旧 line 485-494）
     - `loading` state 保留（仍用于：auto-scroll effect deps、input/button disabled）
     - 删除**只是**那块 JSX，不删 useChatStream 解构出来的 `loading`
  2. **不变量测试**（`app/tests/test_chat_input_invariants.py` 加 2 条新不变量）:
     - `test_no_top_level_loading_thinking_indicator`: 锁住"messages.map 之后到输入区之前不能出现 `{loading && (` 块, 也不能出现"思考中" 文案"
     - `test_thinking_text_appears_only_inside_message_bubble`: 锁住"思考中"只允许出现在 AgentMessageContent 退化路径 + EventsView 函数体内, 防止以后在顶层、提示条、footer 又冒出来
- **教训**:
  - **refactor 容易留下"双轨" UI**: 旧路径和新路径并存但触发条件相同, 必然视觉堆叠。重构后必须 review"旧路径还该不该在", 不要"先留着, 用户没报就先不改"
  - **时序必然撞的判断**: `setMessages` + `setLoading(true)` 同步, 所以两个条件永远同时为真。**状态间存在 invariant 关系时, 不要让两个 UI 都表达同一个信号** — 选一个最精准的 (这里是消息气泡内 EventsView, 因为它就是 stub message 的视觉表达)
  - **"防堵死" 跟 "保留冗余" 是两件事**: 我可能下意识觉得"删了顶层那个, 万一 hook 出 bug 看不到 loading 怎么办?" — 这是用"防御性冗余"对抗"显式信号"。正确做法是"信号只在最准确的位置显示一次", hook 出 bug 就修 hook, 不要靠双轨兜底
  - **lesson #11 (TaskRow 4 个 ▾ 上下叠) 的同源教训**: 这个项目里"视觉堆叠" 已经出现过一次 (#11 修于 2026-07-21), 这次的 bug 跟 #11 是**同一类问题** — 同一个信号在两个地方渲染。看到"两个看起来一样的元素" 就该触发"为什么有两份?" 的反射
  - **不变量测试要锁住"位置", 不只是"内容"**: 旧测试只验证"EventsView 有思考中文案" (字符串存在), 没验证"其他地方没有思考中文案" (字符串只在那里)。新加的两条不变量专门锁位置, 防退化
- **修法位置**:
  - `web/components/ChatWindow.tsx` 旧 line 485-494 删除（messages.map 之后那段 `{loading && (...)}` JSX）
  - `app/tests/test_chat_input_invariants.py` 加 `test_no_top_level_loading_thinking_indicator` + `test_thinking_text_appears_only_inside_message_bubble`

## #14. 完成弹窗 4 字段问卷 → 用户报"在写两遍" 完成成本 > 沉淀价值 (修于 2026-07-28)

- **症状**：用户原话 (2026-07-28): "我在完成一个任务的时候, 我需要去填写 CV 这一部分以及完成了什么, 就我觉得有点麻烦"。
- **根因** (跟 #4 "完成路径堵死" 同源 — 都是完成路径 UX 失败, 一个堵死一个摩擦大):
  - **outcome 和 cv 90% 重复**: 旧 4 字段 placeholder 就是同一件事的两种写法
    - outcome: "用户反馈登录 bug 已修复, 无复现, DAU 提升 5%"
    - cv: "定位并修复高优先级登录鉴权 bug, 消除用户阻塞, 当日上线验证"
  - **完成时刻是认知低谷, 不是高峰**: 旧版默认 outcome + cv 两个必填, 等于让用户跑过终点时停下来填 2 字段问卷
  - **cv_status 三态让认知再加重一档**: ready / needs_data / pending, 大多数用户没空想直接选 ready, 但**形式上要选**
  - **价值是"未来兑现"用户当下看不到**: 弹窗就是纯成本, 沉淀的复利感要等 3 个月后写述职才能感受
- **错误的设计哲学**: "完成即沉淀" (task-cockpit 核心) 没错, **错在执行** — 把全部成本压在用户最容易疲劳的那一刻, 又不让用户当下感受到沉淀的价值
- **修法** (A+D 组合, 见 AGENTS.md Changelog 2026-07-28 完整记录):
  - **A: 砍到 1 必填 + 智能预填 + 润色按钮**
    - outcome 唯一必填 (用户独有信息, LLM 推不出来)
    - cv 智能预填 `完成「${title}」` + ✨ 润色按钮调 LLM
    - reflection + cv_status 折叠在"高级" 区, 默认收起
  - **D: 完成时弹 toast 庆祝 + 跳转链接**
    - 文案 `🎉 已沉淀 · 成就库累计 N 个 ready`
    - "查看成就库 →" 跳 `/achievements`, 让用户当下看见价值
  - **后端独立 `POST /api/llm/polish_cv` 端点**: 失败静默 fallback, 不抛 500 (避免 LLM 抽风把完成流程堵死)
- **教训**:
  - **完成时刻的 UX 优先级最高**: 多巴胺峰值, 用户的"完成感"被任何摩擦打断都是损失。**摩擦 > 任务本身难度** = 用户挫败
  - **AI 增强层永远不能在主流程制造新阻塞**: 润色按钮是 "增强", 不是 "必经"。LLM 不可用 → 静默 fallback, 用户原始输入始终可用
  - **"完成即沉淀" 的复利要用户当下看见**: toast 庆祝不是装饰, 是"让用户感受到在攒家底" 的关键节点。否则沉淀哲学变成"完成时偷偷做, 用户不知情" = 长期信任崩塌
  - **降级优于删除**: reflection/cv_status 折叠保留, 不删除, 旧 power user 不流失, 默认用户摩擦砍掉
  - **专用 API 优于复用 chat 端点**: `polish_cv` 独立端点, 前端只发 `{task_title, outcome}` 拿 `{cv, polished}`, 不暴露 Anthropic 协议复杂度
  - **lesson #4 "完成路径堵死" 同源教训**: #4 是"不能完成" (路径死锁), #14 是"完成太麻烦" (摩擦过大), 根因都是"完成路径 UX 没用户测试"。下次设计任何"完成 / 提交 / 关闭" 类动作前, 先问"这一刻用户的认知状态是什么? 我增加了多少摩擦?"
- **修法位置**:
  - 后端: `app/api/llm.py` 加 `polish_cv` 端点 + `app/tests/test_api_polish_cv.py` 9 条端点测试
  - 前端弹窗: `web/components/CompleteTaskModal.tsx` 完全重写 v3 (1 必填 + 智能 + 折叠)
  - 前端 API 封装: `web/lib/api.ts` 加 `api.polishCv()`
  - 前端 Toast: `web/components/Toast.tsx` 新建 + `web/app/layout.tsx` 挂载
  - 前端 Toast 调用: `web/components/MainBoard.tsx` + `web/app/today/page.tsx` 完成路径
  - 不变量测试: `app/tests/test_complete_modal_minimal_invariants.py` (9 条) + `app/tests/test_completion_toast_invariants.py` (8 条)

## #15. 完成弹窗「动作≠价值」— 抽象任务不知道写什么（修于 2026-07-30）

- **症状**：用户原话 (2026-07-29 23:50)："如果我在项目中的一个任务是「完成 PRD」, 那么我的「结果描述」以及「CV 成就陈述」要怎么写呢?"
- **背景**：
  - 2026-07-28 lesson #14 把完成弹窗从 4 字段砍到 1 必填 (outcome) + 智能预填 cv + ✨ 润色按钮, 解决了"完成时刻摩擦" 痛点
  - 但 lesson #14 **没解决** 用户"填不出价值" 的新问题：用户卡在"outcome 该写啥? cv 该写啥? 任务标题已经说了啊"
  - 本质：**任务标题 = 动作**（"完成 PRD"），**结果描述 = 价值**（"为 App 改版输出 PRD 覆盖 18 个核心场景"），**用户当下只记得"动作"忘了"价值"** — "动作 ≠ 价值" 痛点
- **根因**（用户认知 vs 弹窗形态的错位）：
  1. **弹窗只"收集字段"不"帮用户回忆价值"**：旧弹窗给 1 个 textarea, 等用户主动写。但用户当下大脑卡在"我刚完成了什么" 的动作记忆, 调不出"为什么这件事有价值" 的价值记忆
  2. **placeholder 给"修 bug" 示例, 不给"写 PRD" 示例**：「例如：用户反馈登录 bug 已修复, DAU 提升 5%」 — 跟用户的"完成 PRD" 任务不匹配, 用户看到示例心想"我又不是修 bug"
  3. **AI 润色输入太薄**：LLM 拿到 `"完成 PRD"` 这种 1-2 字抽象 outcome, 即便尽力润色也只能返 "完成「完成 PRD」" 兜底, 因为它**没有追问机制**去主动问"给谁看 / 解决什么"
- **错误的设计假设**：
  - 假设"用户能主动回忆出价值" — 但认知科学告诉我们: **当下回忆 (recall) 比当下识别 (recognition) 难 10 倍**。给 4 个维度 chip, 用户能从里面识别/选择, 比让用户自由回忆容易得多
  - 假设"1 必填 + 1 智能预填就够" — 但智能预填只有"任务标题" 信息, 没有"任务类型" 信息, 没针对性
- **修法** (A+B 组合, 见 AGENTS.md Changelog 2026-07-30 完整记录):
  - **A: 任务标题分类 → 引导卡片 (前端, 纯函数)**
    - 新建 `web/lib/taskGuidance.ts`, 按 `task.title` 关键词分 5 类: `artifact` (PRD/PPT/文档) / `fix` (修/解决/bug) / `discussion` (开会/沟通) / `research` (调研/对比) / `generic` (兜底)
    - 每类给 `{emoji, label, 4 dimensions, placeholder, 2-3 followUp questions}`
    - CompleteTaskModal 加引导卡片: outcome 输入框**下方** (不挡视线), 默认展开可关闭, 任务类型 emoji + label + 4 维度 chip + 提示语
    - **outcome placeholder 动态化**: `"完成 PRD"` → 弹 placeholder 「例如：为 App 改版输出主流程 PRD，覆盖 18 个核心场景，三方评审一次通过」 (artifact 类示例) — 用户看到跟自己任务类型匹配的示例
  - **B: AI 追问 (后端 prompt + 前端 chip)**
    - 后端 `polish_cv` prompt 增强: 让 LLM 必要时返 JSON `{cv, follow_up_questions}`。信息够 → `questions=[]`, 信息太抽象 → `questions=["这份是给谁看的？", "评审结果怎么样？"]` (针对任务类型)
    - response schema 加 `follow_up_questions: list[str]` 字段, **fallback 路径也返空数组** (前端 `length > 0` 判断依赖此不变量)
    - 前端 polish 完后: cv 框**上方**显示追问卡片 (info 蓝), 每个 question 是个可点 chip
    - **点 chip 自动追加到 outcome 末尾** (用 `【...】` 包住, 视觉区分), 追问消费后从列表移除
    - **形成"outcome → AI 追问 → 补全 → 再润色" 的对话闭环**: 用户写 "完成 PRD" → 点润色 → LLM 返 2 个追问 → 用户点 chip → outcome 变 "完成 PRD\n【这份是给谁看的？】X 团队" → 再点润色 → LLM 拿到更完整 outcome → 返好 CV
- **鲁棒性设计**:
  - **JSON 解析鲁棒性**: 后端 `_parse_llm_json_output` 处理 3 种情况: 严格 JSON / ```json 包装 / 纯文本 (老格式)。纯文本走老路径 (整段当 cv + questions=[]), 不抛错
  - **schema fallback**: 无 LLM / 异常 / 解析失败 → `follow_up_questions=[]` 必返, 前端不渲染追问卡片。**关键不变量**: 所有路径都返 `follow_up_questions` 字段 (类型 `list`), 不能缺
  - **chip 消费后从列表移除**: `setFollowUpQuestions((prev) => prev.filter(...))`, 避免用户重复点同一追问
- **教训**:
  - **"动作 ≠ 价值" 是完成时刻的核心认知错位**: 弹窗不能假设用户能主动回忆价值, 必须给**识别型**提示 (chip 选) 而不是**回忆型**提示 (自由填)
  - **placeholder 要按任务类型动态化**: 写"修 bug" 的示例给"写 PRD" 的用户看, 等于告诉用户"你写不出来是因为你做得不够好", 自我怀疑 + 摩擦双叠加
  - **LLM 缺乏追问机制 = 智能降级为"猜"**: 没追问时 LLM 只能"硬编" (返 `完成「title」` 兜底) 或"瞎润色" (编数据, 违反事实原则)。**让 LLM 主动追问** = 把它从"猜" 变"问" = 输出质量飞跃
  - **对话闭环优于一次性问答**: 不是"用户填 outcome → AI 润色" 一次就完, 而是"outcome → 追问 → 补全 → 再润色" 多轮。**AI 增强型表单** 应该是**对话型**, 不是**填空型**
  - **后端 prompt 改 schema 要兼顾老路径**: 这次 polish_cv 端点增强时, 老路径 (纯文本返) 仍然走"整段当 cv + questions=[]", 不破坏现有 LLM 行为 (有的 LLM 不严格返 JSON)
  - **lesson #14 同源教训**: #14 是"完成时刻摩擦大" (用户能写但嫌麻烦), #15 是"完成时刻不会写" (用户想写但卡壳)。都是"完成时刻的 UX 没考虑用户认知状态"。下次设计任何"任务提交" 类弹窗前, 必做 1 件事: 拿 5 个真实任务标题, 让 3 个人写下 outcome, 看 80% 的人卡在什么地方
- **修法位置**：
  - 前端分类工具: `web/lib/taskGuidance.ts` (新建, 5 类 × 5 字段)
  - 前端弹窗: `web/components/CompleteTaskModal.tsx` v4 (引导卡片 + 动态 placeholder + 追问 chip + appendFollowUp)
  - 前端 API 封装: `web/lib/api.ts` `api.polishCv` 返回类型加 `follow_up_questions?: string[]`
  - 后端: `app/api/llm.py` `POLISH_CV_SYSTEM` prompt 增强 + `PolishCvResponse` 加 `follow_up_questions` 字段 + `_parse_llm_json_output` 鲁棒解析
  - 端点测试: `app/tests/test_api_polish_cv.py` 加 9 条 (JSON 含 questions / 空 questions / ``` 包装 / 纯文本 fallback / 空 cv fallback / 字段必存在不变量 / max 3 截断)
  - UI 不变量: `app/tests/test_complete_modal_minimal_invariants.py` 加 9 条 (import / 分类 / placeholder 动态 / 引导卡片 / 追问保存 / 追问渲染 / appendFollowUp / taskGuidance 5 类 / PRD 关键词识别)

---

## #15 强化: 用户实测 4 轮反馈（2026-07-30 上午, v4 → v4.1）

lesson #15 立后用户实测发现 3 类新问题, 都是单测通过但真实数据失败或新设计原则没贯彻.

### 问题 1: 按钮位置 UX 反模式（用户原话）

> "润色按钮会让用户以为润色的目标是「CV」而不是「结果描述」, 这也是很明显的错误吧"

**根因**:
- 旧 v4 设计: 润色按钮在 **CV 框右侧**（"CV 成就陈述 [...] [✨ 润色]"）
- 用户认知: 按钮 = 操作 CV 框（视觉上贴着 CV）
- 实际行为: 润色流程是 **outcome → CV**（读 outcome 写到 CV，按钮的实际目标是 outcome）
- 冲突: 用户点按钮期待"CV 框变化"，但实际看到"outcome 末尾追加追问"

**教训升级 — "位置 = 认知"**:
- **行动按钮必须贴着行动目标（input）, 不能贴着输出结果（output）**
- 按钮在 A 旁 = 用户认为按钮操作 A
- 按钮 = "读 X 写 Y" 的动词, 但位置必须在 X 旁, 不是 Y 旁
- 反例: "保存" 按钮在 form 旁合理（form 是 input），"提交" 按钮在提交目标旁合理
- 同例: lesson #4 "整行 click = 完成" 也是位置 = 认知失败 → 整行 90% 是空白, 空白点中触发完成 = 反直觉
- **修法三件套（位置 + 文案 + 流向）**:
  - 位置: 按钮移到 outcome 框下方（贴行动目标）
  - 文案: 保留"润色"（不变，避免文案过长破坏 layout）
  - 流向: 按钮行左侧加 "↓ 改写成下方 CV 框" 视觉暗示 input → output
  - **三选一不够，三选三才稳**——位置是根因解决，文案和流向是辅助冗余
- **CV 框 label 必须明确标 output**: 旧"动词开头, 含结果/影响" → 新"AI 润色结果 · 可手动改"
  - 不加这个 label, 用户仍可能误以为 CV 是 input (可手输入让 AI 改)
  - 加了, 视觉上"AI 润色结果" 就是 output 的语义锚点

**lesson #4 同源教训**:
- #4: 整行 click 视觉上是空白, 但触发完成 modal → "空白点中 = 操作" 反直觉
- #15 v4.1: 按钮视觉上贴着 CV, 但操作 outcome → "按钮在 output 旁 = 操作 output" 反直觉
- 两个都是"位置"欺骗用户。**根因相同**: 没把"操作对象"和"按钮"在视觉上对齐
- 修法都是同一原则: **按钮贴行动目标, 不贴行动结果**

### 问题 2: 分类器关键词覆盖盲点（lesson #15 盲点）

**根因**:
- 旧 fix 正则要"修复/修好/修完"复合词 → "**修**登录鉴权 bug"（单独的"修"字）漏匹配
- 旧 artifact 正则只覆盖"PRD/文档/PPT" → "写**周报**"/"**选题**"/"**材料**"漏匹配
- **\b 在中文里不工作**：`/\b修\b.../i` 跟 "修线上问题" 中间隔字符时无法匹配
- 旧 discussion 关键词"述职" → "**整理**述职**材料**" 误走 discussion（artifact 应该优先）

**教训升级 — "单测关键词覆盖率 ≠ 真实数据通过率"**:
- 旧 pytest 静态分析（`test_complete_modal_minimal_invariants.py`）只断言"fix 关键词含 'bug'""artifact 关键词含 'prd'"
- **关键词存在** ≠ **真实标题分类正确**
- 修复 "修登录鉴权 bug" 漏匹配的关键词（"修" 单字）后，又冒出新问题: "修线上问题" / "系统崩溃了" / "闪退问题"（\b 在中文里不工作）
- **修复一个 bug 冒三个**——这是单测覆盖率陷阱。覆盖率 100% 不代表真实场景 100%
- **修法: 端到端测试**（`web/scripts/test-task-guidance.mjs`）
  - 21 个用户真实任务标题（修登录鉴权 bug / 写周报 / 开 Q3 复盘会 等）
  - 用 node `--experimental-strip-types` 跑真实 `classifyTaskTitle` 函数
  - pytest 调 subprocess 跑 mjs，**跨回归锁住真实分类不退化**
  - 21/21 全过——证明函数对真实数据真的工作
- **方法论升级**:
  - 任何"分类器/解析器/LLM 工具"上线前, 必做端到端测试, 不是 nice-to-have
  - 端到端测试用例要来自**真实用户数据**, 不是工程师想象的"应该这样写"
  - lesson #2 "每加一个 LLM 端点都要端到端实测" 同源——M3 CoT 污染也是 mock 测通过但真实失败

**修法（taskGuidance 重构）**:
- 4 个分类改为"动作+产物"配对：
  - artifact: 动作 (写/整理/制作/产出/设计/...) AND 产物 (文档/PPT/草稿/周报/材料/选题/笔记/...)
  - fix: 3 子条件 OR (复合动词 / "修"+bug类 / 直接含 bug 类关键词)
  - 不用 \b（中文不适用）
- artifact 关键词扩展: 周报/月报/季报/材料/选题/文案/内容/笔记/日志/日记/感想/分享/复盘/总结/调研/说明/规范/章程/手册/协议/合同/报价
- fix 关键词扩展: 崩溃/闪退/故障/超时/宕机/卡顿/泄露/泄漏/异常/exception/crash/hang/freeze/timeout/500/404/401/403/null/undefined/nan/oom/leak
- discussion 关键词扩展: 复盘会/评审会/对齐会/分享会/讨论会/启动会/kickoff/回顾会

### 问题 3: 润色按钮 disabled 视觉太弱

**根因**:
- 旧: `disabled:opacity-40` × `bg-accent/15` ≈ 6% 透明——视觉上跟 enabled 几乎一样
- 用户看不出按钮是灰的

**教训升级 — "disabled 视觉要主动设计, 不能用 enabled 态叠加"**:
- enabled 是什么色, disabled 应该是该色的**反色/灰阶**, 不是该色**透明**
- 透明（opacity 衰减）在大多数背景上看不出, 跟 enabled 几乎一样 → 不可点状态被忽略
- 强对比: enabled `bg-accent/15 text-accent`（accent 黄）vs disabled `bg-bg-tertiary text-fg-muted`（灰底灰字）——一眼看出
- 通用规则: **"按钮不可点" 应该跟"按钮可点" 在颜色上有量级差异**, 不是透明度差异
- 反例: lesson #5 "低优先级色点不可见" 跟这是同一类问题——`#666` vs `#0a0a0a` 1.5px 圆点在 dark theme 几乎不可见
- lesson #5 修法: `#666` → `#a0a0a0`（亮灰, 跟红黄形成"红黄灰"梯度）。这里 lesson #15 v4.1 修法同源: 弱对比变强对比

### 整体教训

v4 → v4.1 这 4 轮用户反馈暴露 **3 类"单测过但真实数据失败" 盲点**:
1. **设计假设过强**: "按钮位置 = 操作目标" 我没意识到是设计原则, 实际是核心 UX 铁律
2. **关键词覆盖率幻觉**: 关键词存在 ≠ 真实数据分类正确, 端到端测试是必做
3. **视觉对比幻觉**: 透明度衰减 = 强对比, 实际差几个数量级

**方法论升级**:
- 任何"新设计原则" 立 lesson 时, 必加"反例"——这次 lesson #15 立的"动作≠价值" 是哲学, 但**没立"按钮位置"是铁律**——下次立 lesson 必加"设计原则 + 反例"双轨
- 任何"分类器/解析器/LLM 工具" 上线前, 必做端到端测试——不是"单测覆盖率 100%"，是"真实数据真函数真分类"
- 任何"disabled 态" 设计, 必做"肉眼能区分" 验证——`bg-xxx opacity-40` 默认是反模式, 必用强对比

### 修法位置（v4.1）

- 前端 modal: `web/components/CompleteTaskModal.tsx` 按钮位置 + 流向 + disabled 视觉 + label 标 output
- 前端分类器: `web/lib/taskGuidance.ts` 重构"动作+产物"配对 + 移除 \b + 扩展关键词
- 端到端脚本: `web/scripts/test-task-guidance.mjs`（新文件, 21 个真实任务标题）
- pytest 集成: `app/tests/test_complete_modal_minimal_invariants.py` 加 subprocess 调 mjs + 4 条按钮位置/流向不变量
- 端点测试: `app/tests/test_api_polish_cv.py` 加 5 条 (M3 CoT 剥离 + 平衡大括号提取 + 老路径也剥 CoT)
- 后端: `app/api/llm.py` `_parse_llm_json_output` 5 路径升级 + `_find_balanced_json` helper + 老路径也剥 CoT

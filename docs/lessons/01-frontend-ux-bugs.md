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
- **修法位置**:
  - `web/components/MainBoard.tsx` TaskRow 第一行 onClick (toggleExpand) + 展开 chevron 改指示器 + hover ✅ 按钮加回
  - `app/tests/test_complete_path_invariants.py` #2 改版 (反转) + #5 改版 (加回 hover ✅)
  - `AGENTS.md` Changelog 加 v3 段 (推翻 v2 部分)

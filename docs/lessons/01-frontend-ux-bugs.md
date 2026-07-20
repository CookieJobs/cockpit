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

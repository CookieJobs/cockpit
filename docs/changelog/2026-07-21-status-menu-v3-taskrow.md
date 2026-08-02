---
date: 2026-07-21
slug: status-menu-v3-taskrow
title: TaskRow 整行 click 推翻 v3
status: 现行
supersedes: v2
related_lessons: #11, #12, #13
---

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


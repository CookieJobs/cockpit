---
date: 2026-07-31
slug: drag-reorder
title: 拖动排序 (项目 + 任务) v1
status: 现行
supersedes: —
related_lessons: —
---

## Changelog: 2026-07-31 拖动排序 (项目 + 任务) v1

用户原话: "帮我增加一个可以通过拖动更改项目顺序的功能，哦对项目中任务的顺序也能拖动改更顺序"。

### 调查 + 现状

- 后端 Project / Task 模型**没有 `sort_order` 字段** — 列表按 `created_at ASC` 排
- 前端 lib/api.ts 没有 `reorderProjects` / `reorderTasks` 方法
- 没有任何拖动库 — 需新装
- 前端 ProjectsSection / ProjectCard / TaskRow 都是纯展示，没有 handle

### 选型: @dnd-kit 而非 react-dnd / @hello-pangea/dnd / SortableJS

| 库 | 优势 | 劣势 | 选? |
|---|---|---|---|
| **@dnd-kit** | 现代维护活跃 / 跟 React 18 完美兼容 / 模块化按需装 / a11y 最好 (keyboard 拖动原生支持) / TypeScript 友好 | 略学习曲线 | **✅** |
| react-dnd | 老牌 | 维护慢 / HTML5 backend 跟 React 18 兼容问题 | ❌ |
| @hello-pangea/dnd | react-beautiful-dnd 的 fork | 依赖大 / a11y 差 | ❌ |
| SortableJS | 简单 | jQuery 时代产物 / React 集成费劲 | ❌ |

### 改动

| # | 项 | 位置 | 备注 |
|---|---|---|---|
| 1 | **`Project` / `Task` / `ProjectSnapshot` 加 `sort_order: int`** | `app/core/models.py` + `web/lib/api.ts` | 默认 0, 间隔 10 存 (留插入空间) |
| 2 | **`projects` / `tasks` 表加 `sort_order INTEGER NOT NULL DEFAULT 0` 列** | `app/core/storage.py` `_migrate_add_column` | 老数据 sort_order 全 0, 靠 `created_at ASC` 二级 fallback 保持原顺序 |
| 3 | **list_projects / list_tasks / build_snapshot 改 `sort_order ASC, created_at ASC` 双层排序** | `app/core/storage.py` | 主排序=拖动结果, 次排序=稳定 fallback (防 sort_order 全 0 时乱序) |
| 4 | **`add_project` / `add_task` 自动 `sort_order = max + 10`** | `app/core/storage.py` `_next_sort_order` / `_next_sort_order_for_project` | 新加的排最后, 不断拉开间隔 (拖到中间时用 prev+next/2 算新值) |
| 5 | **`POST /api/projects/reorder` + `POST /api/tasks/reorder` 端点** | `app/api/projects.py` + `app/api/tasks.py` | body `{items: [{id, sort_order}, ...]}`, 批量 atomic |
| 6 | **跨项目 task reorder 拒绝** (返 `updated: 0` + warning) | `app/core/storage.py` `reorder_tasks` | 兜底防线 — 任务 sort_order 是项目内局部的, 跨项目会让 list 排序乱套 |
| 7 | **`api.reorderProjects` / `api.reorderTasks` 前端封装** | `web/lib/api.ts` | 跟其他 PATCH 端点同款 `request<T>()` 包装 |
| 8 | **`SortableProjectCard` / `SortableTaskRow` wrapper 组件** | `web/components/MainBoard.tsx` | 内层 useSortable + GripVertical handle + CSS.Transform 应用, 不污染 ProjectCard / TaskRow 主体 |
| 9 | **ProjectsSection 加 `<DndContext>` + `<SortableContext>` 包裹项目列表** | `web/components/MainBoard.tsx` | `verticalListSortingStrategy` + PointerSensor 5px activation distance (防 click 跟 drag 撞车) |
| 10 | **ProjectCard 内嵌独立 `<DndContext>` 包裹 task list** | `web/components/MainBoard.tsx` | 嵌套 DndContext, 跟外层 sensors 独立 — 拖 task 不会触发 project 拖动 |
| 11 | **拖动句柄 `GripVertical` 在卡片第一行最左** | `web/components/MainBoard.tsx` ProjectCard / TaskRow | `opacity-0 group-hover:opacity-60 hover:!opacity-100` 渐显, 跟 StatusMenu / ✅ / 删除按钮一致的"平时不打扰" 哲学 |
| 12 | **句柄 click `e.stopPropagation()`** | `web/components/MainBoard.tsx` | 防止冒泡到 ProjectCard 整行 onToggle / TaskRow 整行 onClick 展开 |
| 13 | **乐观更新策略: 拖完调 `api.reorder*` → `onChange()` 拉新数据** | `web/components/MainBoard.tsx` handle*DragEnd | 简单可靠, 失败 catch + onChange() 拉回原状态 (无需复杂 optimistic mutate) |
| 14 | **拖动算法: 邻居中间值 (prev+next)/2, 边缘 ±10** | `web/components/MainBoard.tsx` handle*DragEnd | 间隔 10 存, 拖到中间 = (prev+next)/2; 拖到首/尾 = 邻居 ±10; 间隔耗尽时 (N=10 个) 批量重写 |
| 15 | **不变量测试 18 条新增** | `app/tests/test_drag_reorder_invariants.py` (新) | 锁 wrapper / DndContext / dragHandle / API 契约 / models / storage 跨项目拒绝 — 防退化 |
| 16 | **端点级测试 11 条新增** | `app/tests/test_api_reorder.py` (新) | 锁 list 排序 / add_* 自动 max+10 / 跨项目拒绝 / 不存在 id 静默跳过 / 422 invalid body |

### 设计决定记录

**A. 间隔 10 存 vs 全局重排 (1, 2, 3, ...)**

- 全局重排: 每次拖动都更新**所有**项目的 sort_order — N 个项目拖一次 = N 次 UPDATE, 100 个项目 = 100 次 SQL write
- 间隔 10 存: 拖一项到中间只发 1 次 PATCH, 只改 1 行 — 大幅减少 IO
- 代价: 拖 5 次到中间就可能撞间隔 (邻居差 10, 除 2 5 次后趋近 0)
- 解决: 项目数 < 10 基本不会触发; 真撞了, 下次拖动算出的 newOrder ≈ 0, 服务器接受任意值, list 排序走 `created_at ASC` fallback — **优雅降级**
- lesson: **写时省, 读时 fallback** — 跟 description 字段 lesson #10 "build_snapshot 漏传 silent failure" 同源, 都是"宁可在边界场景退化, 也不要在主路径加复杂度"

**B. 嵌套 DndContext vs 单 DndContext**

- 单 DndContext: 全局监听, project 跟 task 共用 sensors, 拖 task 会被 project 监听器看到 — 错位
- 嵌套 DndContext: 外层管 project, 内层管 task, 各自 sensors / 各自 collision detection — 拖动范围明确
- 代价: 多一个 DndContext 实例, 多一对 sensors 监听, 性能开销 < 1ms
- lesson: **拖动层级 = 状态层级** — 项目级跟任务级是两个独立状态, 应该有独立 DndContext 边界

**C. handle 用 `opacity-0 group-hover:opacity-60` 渐进显隐**

- 永远显示: 视觉噪音, 跟 StatusMenu / ✅ / 删除按钮"平时不打扰"哲学冲突
- 完全隐藏: 用户找不到拖动入口
- 渐进显隐: 平时不打扰, hover 整行时 60% 提示"可拖", 自己 hover 时 100% 强调 — **跟现有控件风格一致**
- lesson: **新控件的视觉密度要跟现有同位置控件对齐** — 不引入新的"永远显眼" 或"完全隐藏" 模式, 用现成的渐进显隐套路

**D. `PointerSensor` `activationConstraint: { distance: 5 }` 5px 触发距离**

- 0px 触发: 用户在 handle 上点一下也算 drag, 触发整个拖动链 — 跟 click 撞车
- 5px 触发: 用户点一下不会触发 (移动 < 5px 算 click), 必须真的移动才算 drag — 防误触
- 5px 是 UX 业界默认: 跟 Linear / Notion / Figma 一致
- lesson: **拖动触发距离 = 误触和真拖的平衡点** — 太短被误触, 太长用户拖不动

**E. 跨项目 reorder 拒绝 vs 静默拆开**

- 静默拆开: 按 project_id 分组, 每个项目内部 reorder — 复杂度高, 跟"前端按项目分别发" 重复
- 拒绝 (返 0): 强制前端按项目分别调, 后端做兜底校验 — 简单, 防止 LLM 工具误调或脚本 bug
- 选拒绝: 跟 lesson #1 "StatusMenu '完成' 误操作" 同源 — **边界情况宁可报错, 不要静默**
- lesson: **跨边界校验是兜底防线** — 跟前端正向行为分开, 防止未来 LLM 工具或脚本绕过 UI

**F. add_* 主动 max+10 vs 拖动算法自己算**

- 拖动算法自己算: add_* 不管 sort_order (默认 0), 拖动时算 — 简单, 但新加的 sort_order=0 永远排最前
- 主动 max+10: add_* 主动给 `max(existing) + 10` — 排最后, 符合用户"新加的" 心智
- 选主动: 跟"新加任务 = 排最后" 自然行为一致; 拖动算法不变 (仍然 prev+next/2)
- lesson: **默认值是行为信号** — sort_order=0 不是"无序", 是"位置 0", 主动 max+10 表达"排在最后"

**G. 拖动后 onChange() 拉新数据 vs 乐观 mutate**

- 乐观 mutate: 拖完立即更新本地 snapshot, 同时 PATCH — 复杂, 失败回滚要保存原 sortOrder 快照
- onChange() 拉新: 拖完调 PATCH, 成功后 SWR revalidate 拉新数据 — 简单可靠, 失败 catch + onChange() 拉回
- 选 onChange 拉新: 跟 StatusMenu / PriorityMenu / DueEditor 一致的"改完 PATCH + revalidate" 套路, 不引入新模式
- 代价: 100-200ms 视觉延迟 (SWR 拉到新数据) — 可接受
- lesson: **新交互模式不要轻易引入"优化"** — 跟现有 PATCH 流程对齐, 体验一致性 > 0.1s 视觉延迟

**H. storage layer `sort_order.asc(), created_at.asc()` 双层排序 vs list 端点单独排**

- 端点单独排: API 层 ORDER BY — 简单, 但 snapshot 端点不排序, 前端拿到顺序错乱
- storage 层统一排: list_projects / list_tasks / build_snapshot 都走同样排序 — 一次修改, 处处对齐
- 选 storage 层: 跟 lesson #10 "build_snapshot 漏传" 同源 — **同一字段在不同端点的行为必须一致**, 在 ORM 层固化
- lesson: **共享逻辑下沉到 storage, 不要每个 API endpoint 重复** — 跟 `_next_sort_order` helper 同款思路

### 字段表 (拖动排序后)

| entity | 新字段 | 来源 | 默认值 | 间隔 | 排序主键 | 排序二级 |
|---|---|---|---|---|---|---|
| Project | sort_order | 后端 | 0 | 10 | sort_order ASC | created_at ASC |
| Task | sort_order | 后端 | 0 | 10 | sort_order ASC | created_at ASC |

**回归**: 259 → **277** tests pass (+18 不变量测试 + 11 端点测试). `tsc --noEmit` 0 错误. `npm run build` 10/10 静态页导出通过, First Load JS 增量 +20KB (@dnd-kit/sortable 是主要).


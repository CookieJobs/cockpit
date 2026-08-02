---
date: 2026-07-28
slug: achievements-hierarchy
title: 成就库 v2 项目层级
status: 现行
supersedes: —
related_lessons: —
---

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


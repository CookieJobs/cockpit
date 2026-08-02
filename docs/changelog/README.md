# Cockpit Changelog — 项目演化决策史

> 给后面接手 / 跨时间回看的 agent 用。每条 Changelog 是"变更 + 设计理由 + 推翻关系"的完整记录。
>
> 跟 [`docs/lessons/`](../lessons/README.md) 是**互补关系**：
> - **Lessons** = 踩坑（症状 → 根因 → 教训），是**负面**教训库
> - **Changelog** = 决策（变更 + 设计理由 A/B/C/D），是**正向**演化史
>
> Changelog 里有 lessons 引用不出来的两类信息：
> 1. **推翻链**（v1 → v2 → v3 关系）—— "为什么不能照着 v1 改"
> 2. **设计哲学 A/B/C/D 决定** —— "为什么选 X 不选 Y"，是**踩坑前**的完整思考

## 目录（按时间倒序，状态现行优先）

### 现行版本

| 日期 | 主题 | 关联 Lessons | 详情 |
|---|---|---|---|
| 2026-08-01 | 时区 bug 修复 —「今天」显示成「明天」 | [#19](../lessons/06-timezone.md) | [→](2026-08-01-timezone-fix.md) |
| 2026-08-02 | **目标模式启动 — 主目标定为"AI 工作流记忆 → 履历生成 OS"** | — | [→](2026-08-02-goal-mode-launch.md) |
| 2026-08-02 | **v0.3.1 主动建议机制 — outcome 停笔 1.5s 后 AI 自动给 cv 建议** | [#14 #15](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.3.1.md) |
| 2026-08-02 | **v0.3.3 状态机端到端测试 + 修空 answers 升级 bug** | — | [→](2026-08-02-v0.3.3.md) |
| 2026-08-02 | **v0.4.2 跨项目 CV 视图 — 新页 /cv + cv-template.ts + 23 个端到端测试** | [#22](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.4.2.md) |
| 2026-08-02 | **v0.3.4 润色质量升级 — POLISH_CV_SYSTEM 软改硬 + few-shot + 9 个测试** | [#15](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.3.4.md) |
| 2026-08-02 | **v0.3.5 沉淀质量卡片 — /achievements 顶部 3 指标 + 评级 + 52 个端到端测试** | [#14](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.3.5.md) |
| 2026-08-02 | **v0.3.2 智能追问补全闭环 — /report 顶部 info 卡片 + 待补条目列表** | [#15](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.3.2.md) |
| 2026-08-02 | **v0.4.1 时间线 toggle — /achievements 加按项目/按时间切换 + localStorage 持久化** | — | [→](2026-08-02-v0.4.1.md) |
| 2026-08-02 | **v0.4.3 动词分布 — 沉淀质量卡片展开 + 条形图 + 12 个端到端测试** | — | [→](2026-08-02-v0.4.3.md) |
| 2026-08-02 | **v0.5a MCP 集成 — cockpit MCP server + 5 工具 + 7 端到端测试 + SKILL.md** | [#22](../lessons/01-frontend-ux-bugs.md) | [→](2026-08-02-v0.5a.md) |
| 2026-08-01 | 主题切换 (light / dark) | [#17](../lessons/05-theme-system.md) | [→](2026-08-01-theme-toggle.md) |
| 2026-07-31 | 拖动排序 (项目 + 任务) | — | [→](2026-07-31-drag-reorder.md) |
| 2026-07-30 | 完成弹窗 v4.1 — 按钮位置 UX + 分类器盲点 | [#15](../lessons/01-frontend-ux-bugs.md) | [→](2026-07-30-complete-modal-v4-1.md) |
| 2026-07-30 | 完成弹窗 v4 — 任务引导卡片 + AI 追问 | [#15](../lessons/01-frontend-ux-bugs.md) | [→](2026-07-30-complete-modal-v4.md) |
| 2026-07-28 | 成就库 v2 项目层级 | — | [→](2026-07-28-achievements-hierarchy.md) |
| 2026-07-28 | 完成弹窗极简化 A+D | [#14](../lessons/01-frontend-ux-bugs.md) | [→](2026-07-28-complete-modal-minimal.md) |
| 2026-07-23 | P2 换冷色蓝 (跟 P1 暖色撞色) | — | [→](2026-07-23-priority-p2-blue.md) |
| 2026-07-23 | ChatWindow 双"思考中"视觉堆叠修复 | [#13](../lessons/01-frontend-ux-bugs.md) | [→](2026-07-23-chatwindow-thinking.md) |
| 2026-07-22 | Priority 升级 P0/P1/P2/P3 + badge | — | [→](2026-07-22-priority-p0p1p2p3.md) |
| 2026-07-22 | blocked / draft inline edit (Agent 字段人手可改) | — | [→](2026-07-22-blocked-draft-inline.md) |
| 2026-07-22 | StatusMenu 状态融合 + 移到右侧 (v3) | — | [→](2026-07-22-status-menu-fused.md) |
| 2026-07-22 | StatusMenu 短进度条 + 项目内"已沉淀"子区 | — | [→](2026-07-22-status-menu-progress.md) |
| 2026-07-22 | 消息泡 Markdown 升级 (react-markdown + GFM) | — | [→](2026-07-22-markdown-upgrade.md) |
| 2026-07-21 | StatusMenu 整行 click 推翻 v3 (TaskRow) | [#11 #12 #13](../lessons/01-frontend-ux-bugs.md) | [→](2026-07-21-status-menu-v3-taskrow.md) |
| 2026-07-20 | 兑现 #1 周报/述职 workspace + 4 项 UX 升级 | — | [→](2026-07-20-report-workspace.md) |
| 2026-07-16 | 借鉴 task-cockpit 8 项 | — | [→](2026-07-16-task-cockpit-borrow.md) |

### 已被推翻的旧版本（**别照着改**，看推翻关系）

| 日期 | 主题 | 推翻于 | 详情 |
|---|---|---|---|
| 2026-07-17 | StatusMenu 状态菜单化 v2 | [2026-07-21 v3](2026-07-21-status-menu-v3-taskrow.md) | [→](2026-07-17-status-menu-v2.md) |

## 推翻链速查

遇到"为什么不能照 X 改"时，按这条链追溯：

- **StatusMenu**: 2026-07-17 v2 → **2026-07-21 v3 推翻**（整行 click = 完成 反直觉）→ 2026-07-22 短进度条 v3 续 → 2026-07-22 状态融合 v3 续
- **完成弹窗**: 2026-07-28 极简化 A+D → 2026-07-30 v4 任务引导 → 2026-07-30 v4.1 按钮位置
- **Priority 视觉**: 2026-07-22 P0/P1/P2/P3 badge → 2026-07-23 P2 换冷色蓝

## 使用方式

1. 接手项目时**先读 AGENTS.md 顶部 + 这个 README 索引** —— 知道项目演化主线
2. 改相关模块前，**先看"现行版本"表的关联 Lessons**（教训） + **本目录对应详情文件**（决策理由 A/B/C/D）
3. 看到"已被推翻"标记时**别照着改**——去看推翻后版本
4. 每次大改 / 新增功能，**新建一个 Changelog 文件**（命名 `YYYY-MM-DD-slug.md`），加 frontmatter 元信息（日期/版本/状态/推翻关系/关联 lessons），同时在本 README 索引加一行

## 与 AGENTS.md 主文件的关系

- **AGENTS.md**（项目根）保留：项目一句话、核心路径、LLM 后端约定、测试入口、设计哲学、Lesson 索引
- **本目录**保留：Changelog 完整内容（变更 + 设计理由 A/B/C/D + 推翻关系）
- 拆分动机：AGENTS.md 涨到 1300+ 行时入口不可读，Changelog 拆出来既保历史又省 token。Lessons 拆分原则（2026-07-20 立）扩展到 Changelog

# 04 — 测试方法论 Lessons

> 测试不是越多越好, 是覆盖到位 + 跑得快 + 失败信息可执行。

## #6. 端到端 UX 路径静态分析测试 (2026-07-17 立)

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

**2026-07-20 立的新一批 invariant 测试**：
- `test_archive_project_invariants.py` — 锁住项目归档 UI (ProjectsSection / ProjectCard 必须有 Archive 按钮)
- `test_report_workspace_invariants.py` — 锁住 /report workspace (页面 + 模板 + 述职只取 ready)
- `test_chatwindow_refactor_invariants.py` — 锁住 ChatWindow 重构 (hook 必须用, 不能直接调 chatStream)

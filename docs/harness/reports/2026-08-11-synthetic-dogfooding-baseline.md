# Synthetic Dogfooding Baseline — 2026-08-11

## 决策

Synthetic Dogfooding Harness v1 可以成为 Cockpit 的发布前工作流与事实边界回归，现已纳入
`make project-gate`。它**不**构成 `GOAL.md` v0.3/v0.4 的真实用户验证证据。

## 运行证据

- Run：`/tmp/cockpit-synthetic-baseline.Ho0sZF`（临时制品，不纳入仓库）
- Persona：B2C 产品经理、工程团队负责人、增长运营负责人、独立设计师
- 事件：16 条，四人各四周；每人 1 条 `needs_data` 路径
- 入口：公共 Projects / Tasks / Task completion / Achievements HTTP API；不直写 ORM 或 SQL
- 输出：每 Persona 四份周窗口报告与一份完整周期覆盖报告，均走现有 `product_weekly` 模板

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| 完成率 | 100% | 16/16 合成工作事件完成并沉淀 |
| Ready 率 | 75% | 12/16 有充分初始证据；4 条保留补数路径 |
| 周覆盖率 | 100% | 16/16 Persona×周窗口存在输出 |
| 完整周期覆盖率 | 100% | 4/4 Persona 有完整周期输出 |
| P0 输出泄漏 | 0 | 无未知 ID、无 `needs_data` 成就进入报告 |
| Recovery 率 | 0% | v1 尚未模拟“回答追问并修订 CV”闭环 |

## CTO 结论与下一轮

本轮证明了“事件 → API 写入 → ready-only 报告 → 审查”的基础链路在隔离环境可重复执行，
并能对未就绪内容进入输出实施 P0 阻断。

下一轮应补上 **follow-up recovery**：针对至少一个 `needs_data` 事件，模拟用户回答追问、
补齐证据并修订 CV，再确认升级到 `ready` 后的周报输出仍只包含有依据的陈述。完成后，才将
Recovery 率视为有解释力的指标。

真实验证仍需独立开展：两周真实自用、至少 20 条真实成就、可直接采用率与已确认的零事实
编造，均按 `docs/GOAL.md` 记录，绝不可由本报告替代。

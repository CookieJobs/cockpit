# Synthetic Dogfooding Baseline — 2026-08-11

## 决策

Synthetic Dogfooding Harness v1 可以成为 Cockpit 的发布前工作流与事实边界回归，现已纳入
`make project-gate`。它**不**构成 `GOAL.md` v0.3/v0.4 的真实用户验证证据。

## 运行证据

- Run：`/tmp/cockpit-synthetic-baseline.Ho0sZF`（临时制品，不纳入仓库）
- Persona：B2C 产品经理、工程团队负责人、增长运营负责人、独立设计师
- 事件：16 条，四人各四周；4 条初始 `needs_data` 路径，其中 1 条完成补证恢复
- 入口：公共 Projects / Tasks / Task completion / Achievements HTTP API；不直写 ORM 或 SQL
- 输出：每 Persona 四份周窗口报告与一份完整周期覆盖报告，均走现有 `product_weekly` 模板

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| 完成率 | 100% | 16/16 合成工作事件完成并沉淀 |
| Ready 率 | 81.25% | 12 条初始 ready，加 1 条补证并修订 CV 后 ready |
| 周覆盖率 | 100% | 16/16 Persona×周窗口存在输出 |
| 完整周期覆盖率 | 100% | 4/4 Persona 有完整周期输出 |
| P0 输出泄漏 | 0 | 无未知 ID、无 `needs_data` 成就进入报告 |
| Recovery 率 | 25% | 1/4 初始 `needs_data` 事件完成“回答追问 → 修订 CV → ready”闭环 |

## CTO 结论与下一轮

本轮证明了“事件 → API 写入 → ready-only 报告 → 审查”的基础链路在隔离环境可重复执行，
并能对未就绪内容进入输出实施 P0 阻断。

本轮已补上 **follow-up recovery**：独立设计师在首周反馈后，回答追问并修订 CV；只有最终
有“增加 6 条咨询表单”证据锚点的 ready 版本进入完整周期报告。其余 3 条仍保持未恢复，持续
覆盖“未就绪内容不得进入输出”的边界。

真实验证仍需独立开展：两周真实自用、至少 20 条真实成就、可直接采用率与已确认的零事实
编造，均按 `docs/GOAL.md` 记录，绝不可由本报告替代。

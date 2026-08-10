# Project Harness v1 — 本地质量门

## 决策

将单一的 Achievement Distillation Harness 升级为项目级本地质量门：能力注册表声明已实现能力、未来能力、依赖和回归命令；`make project-gate` 汇总其结果并输出稳定 JSON。

## 关键约束

- `future` 能力只报 capability gap，不阻塞当前发布。
- 已实现能力缺少声明依赖或测试失败即阻塞。
- 新增 L2 宪法测试覆盖不可逆删除确认、事实不足不进 ready、正式输出只用 ready、API 不得直接覆盖 readiness。
- MCP 被纳入 gate，确保“接入中心能写配置”与“实际 server 可启动”不脱节。

## 用户可见结果

未补全证据的成就不会进入任何正式报告或 CV 输出；报告页和成就库页不再提供直接升 `ready` 的捷径，用户须通过补充证据路径恢复可用性。

## 后续

本版本只建立基础层。下一阶段 Product Scorecard v1 再用真实自用数据衡量采纳率、兑现速度和回看价值，不以自动化分数替代用户价值。

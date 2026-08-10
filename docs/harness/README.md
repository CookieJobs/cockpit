# Harness

Cockpit 的 Harness 是本地质量门，不是“AI 自己宣布产品变好”的装置。它验证产品
不变量、能力边界和可复现的关键工作流；真实用户采纳仍需按 `docs/GOAL.md` 单独衡量。

## 本地质量门

```bash
make project-gate
```

它运行成就蒸馏、报告组合、MCP 写入、宪法边界和 Synthetic Dogfooding 的注册能力。
`refiner`、`git_candidate`、`composer` 仍是明确展示的未来能力缺口，不会被伪装为已实现。

## Synthetic Dogfooding Harness v1

```bash
make synthetic-dogfood
# 或保留一次运行的制品：
.venv312/bin/python app/scripts/run_synthetic_dogfooding.py --output /tmp/cockpit-synthetic-run
```

它用四个虚构 Persona（产品经理、工程负责人、增长运营、独立设计师）在彼此隔离、临时
丢弃的 SQLite 数据库内，经过 Cockpit 的公共 HTTP API 重放四周工作事件。制品包括：

- `replay.json`：API 返回的成就快照；
- `reports/<persona>/week-*.json` 与 `full-window.json`：经现有周报模板生成的 ready-only 输出；
- `review.json` 与 `weekly-review.md`：完成、就绪、覆盖与泄漏检查。

它不访问 `~/.cockpit`，不包含任何真人、真实公司或生产数据。结果只能证明“模拟工作流
与事实边界通过”，不能证明用户留存、直接采用率或产品市场匹配。

## 基线

见 [2026-08-11 Synthetic Dogfooding Baseline](reports/2026-08-11-synthetic-dogfooding-baseline.md)。

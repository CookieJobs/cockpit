# Project Harness v1：基础质量门设计

## 目标

建立一个本地、可重复执行的项目级质量门。它把 Cockpit 的产品宪法、已实现能力与现有测试汇总为可判定的发布结论，使 AI CTO 的每轮迭代都先证明没有破坏“服务人、本地优先、事实优先、用户掌控”的约束。

本轮只建设**基础层**：能力注册、宪法/L2 回归、依赖预检，以及统一的本地 `project-gate`。不建设趋势仪表盘、云端 CI、真实模型评分调度或自动发布。

## 背景与问题

现有 `app/harness/` 已能评估成就蒸馏，但它是单能力 Harness，不是项目总门。当前还存在三类风险：

1. 架构文档定义了 L2 宪法测试和发布门，但仓库没有可执行的 `app/tests/constitution/`。
2. 当前蒸馏数据集混合“当前能力”和“目标能力”；把全部案例作为发布判断会把 capability gap 误报为当前版本退化。
3. MCP 是既定 v0.5a 能力，但运行环境缺少 optional `mcp` 依赖时，测试只能在执行后失败，无法给出明确、可行动的预检结论。

此外，报告输出的 `ready` 边界必须由程序统一维护：未就绪资产不能进入正式输出，任意界面也不能无证据提升其状态。

## 非目标

- 不让 AI 自动修改、合并或发布代码。
- 不把 Harness 分数当成用户价值或替代 dogfooding。
- 不引入云端服务、远程 telemetry 或 GitHub Actions。
- 不实现 Refiner、Git 采集、Composer 的未来能力；只注册其状态，不把它们写成可通过的当前能力。

## 架构

```
docs/harness/capabilities-v1.yaml
  └─ 每项能力的状态、风险、验证命令与发布范围
                 ↓
app/harness/project_gate.py
  ├─ 读取注册表并验证结构
  ├─ 预检 Python / Node / 可选依赖
  ├─ 执行本轮纳入发布范围的能力命令
  ├─ 汇总为稳定 JSON
  └─ 任一 blocking 检查失败时非零退出
                 ↓
make project-gate
  └─ 本地迭代和发布前的唯一项目级入口
```

每项能力都有清晰边界：

| 能力 | 当前状态 | 本轮 Gate 责任 |
|---|---|---|
| `achievement_distillation` | 已实现 | 运行当前基线案例与事实安全检查；目标能力案例只报告缺口，不阻塞当前基线 |
| `report_composition` | 已实现 | 证明只有 `ready` 成就可进入正式输出，且无 UI/API 状态绕过 |
| `mcp_write_path` | 已实现但环境可选 | 声明需要 `mcp`；安装时运行 MCP 协议测试，未安装时明确阻塞该能力的发布 |
| `constitution` | 本轮新增 | 运行确定性 L2 测试，覆盖不可逆确认、事实不编造、本地优先和 AI 不可绕过质量门 |
| `refiner` / `git_candidate` / `composer` | 未实现或未纳入本轮 | 注册为 future，不进入当前发布结论 |

## 关键决策

### 1. Gate 有两种结果，不混淆

- `blocking_failure`：已承诺且纳入当前版本的能力不安全、不可运行或回归；退出码非零。
- `capability_gap`：注册为 future 的能力尚未实现；写入报告但不影响当前版本通过。

因此，成就蒸馏的 release gate 只运行 `current_baseline` suite。包含新能力预期的 `target_capability` suite 保留为 roadmap 信号，不作为当前版本失败。

### 2. 依赖是能力契约的一部分

MCP 被标记为 `implemented` 时，`mcp` 必须在当前 Python 环境可导入；否则 `mcp_write_path` 是 blocking failure，报告必须给出安装命令 `pip install -e '.[dev]'`。不把缺依赖伪装成测试失败或跳过。

### 3. 状态升级不等于用户点击

`ready` 是可进入正式输出的证据结论，而不是前端可自由编辑的标签。本轮会将报告模板的输入限制为 `ready`，并移除或收紧绕过统一写入边界的升级入口。补全追问或完成有证据的 CV 后，才可经既有 storage 规则进入 `ready`。

### 4. 宪法测试用确定性程序证明

本轮的 L2 不调用真实 LLM。测试程序边界和工具/存储边界：

- 未完成二次确认不得执行删除。
- 无依据数字、实体或 ownership 升级必须被运行时事实 guardrail 拒绝。
- 外部 Agent/MCP 的写入必须经过同一完成质量门。
- 报告与 CV 输出不得使用非 `ready` 成就。

面向自然语言的“是否拒绝团队版”等 Agent 行为测试，需要独立的 Chat Agent Harness，留到相应能力实现时注册；本轮不制造 mock prompt 测试的虚假安全感。

## 接口与输出

注册表由 `CapabilitySpec` 表示，至少包含：`id`、`status`（`implemented` / `future`）、`risk_level`、`release_suite`、`command` 与 `required_dependencies`。

`project_gate` 输出稳定 JSON：

```json
{
  "passed": false,
  "checks": [{"id": "mcp_write_path", "status": "blocking_failure", "reason": "missing_dependency:mcp"}],
  "capability_gaps": ["refiner"],
  "blocking_reasons": ["mcp_write_path:missing_dependency:mcp"]
}
```

只有 `implemented` 且 `release_suite: true` 的能力可以产生 blocking failure。`future` 能力只能进入 `capability_gaps`。

## 验收标准

1. `make project-gate` 生成可解析 JSON；任何 blocking failure 返回非零退出码。
2. 不安装 `mcp` 时，报告把 MCP 标为明确的 `missing_dependency:mcp`；安装后可运行 MCP 测试。
3. `current_baseline` 蒸馏 gate 与 `target_capability` 缺口分开报告；未来案例不会误阻塞当前能力。
4. L2 宪法测试覆盖上述四个可确定验证的边界，并纳入项目 gate。
5. `needs_data` 和 `pending` 不能进入正式报告/CV 输出，也不能由报告 UI 直接提升至 `ready`。
6. 全部现有后端、前端类型检查以及本轮新增测试通过；不运行 `next build`。

## 后续衔接

基础层稳定后，才启动 `Product Scorecard v1`：从 trace、编辑反馈和真实 dogfooding 中形成每周 CTO 决策单。该系统采集人类价值信号，但不自动替用户做产品选择或发布。

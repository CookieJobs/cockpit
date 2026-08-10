# Synthetic Dogfooding Harness v1：多 Persona 工作流仿真

## 目标

用可复现的多 Persona 工作周仿真，验证 Cockpit 的核心闭环是否在不同职业叙事下成立：工作事件 → 任务 → 成就沉淀 → 追问补全 → 周报 / 月报输出。

该 Harness 用于快速发现产品路径、事实边界和输出覆盖问题；不用于替代真实 dogfooding、种子用户访谈或商业判断。

## Persona 与范围

首版固定四个 persona，每个都有公司背景、岗位、3–5 个并行项目、四周事件流和可核验事实：

| ID | Persona | 用途 |
|---|---|---|
| `product_manager` | B2C 产品经理 | 跨团队需求、上线、数据复盘 |
| `engineering_lead` | 技术 TL | 故障、重构、发布、协作归因 |
| `growth_operator` | 增长运营 | 活动、内容、渠道、指标与归因 |
| `independent_designer` | 独立设计师 | 客户项目、交付、反馈、作品叙事 |

每个 persona 使用独立临时 SQLite 数据库。仿真只能调用 Cockpit 的公开 task / achievement API 与报告生成函数；不直接写 ORM 表，不调外部服务，不共享用户数据。

## 数据流

```
版本化 persona fixture
  → 每周工作事件（具备事实锚点）
  → 真实 API：项目 / 任务 / complete
  → 对低证据条目补全 follow-up
  → 真实报告模板：4 份周报 + 1 份月报
  → 审阅器：覆盖率、非 ready 泄漏、事实编造、可用性缺口
  → JSON 报告 + capability gap
```

“月报”在 v1 复用当前 `product_weekly` 模板和本月时间范围；它验证共享数据源及覆盖，不声称已交付最终月报产品模板。

## 指标与判定

每个 persona 输出：

- `completion_rate`：计划事件是否均形成已完成成就；
- `ready_rate`：沉淀后可进入输出池的比例；
- `weekly_coverage_rate`：当周有事实锚点的事件是否出现在周报；
- `monthly_coverage_rate`：四周 ready 成就是否进入月度输出；
- `unsupported_fact_count`：输出是否含 fixture 未提供的数字、实体或 ownership；
- `recovery_rate`：needs_data 是否可经完整 follow-up 进入 ready。

P0：任何输出事实编造、任何非 ready 成就进入正式输出。P1：预期完成事件缺失、追问无法恢复、周报覆盖不足。所有指标都必须保留到 persona 原始事件的可追溯映射。

## 审阅边界

首版先以确定性审阅器为准：报告条目只能来自 ready achievement 的 `cv` / `outcome` / `title`，并用 fixture 词元和数字锚点检查。可选 LLM Judge 仅作为补充观察，不决定 gate。

多个执行 Agent 可并行运行 persona，但各自只处理一个 fixture 与一个临时数据库。汇总器不接受 Agent 自述，只读取结构化运行结果。

## 非目标

- 不模拟真实心理摩擦、长期留存或支付意愿。
- 不创建用户真实数据，不访问真实 Git / 对话历史。
- 不实现 Git 集成、Refiner 或最终月报模板。
- 不允许 persona 自动把候选成就写为 ready 而绕过统一质量门。

## 验收

1. 单个命令可运行四个 persona 的四周仿真，并生成稳定 JSON。
2. 每个 persona 独立数据库且无共享数据。
3. 每位 persona 产生 4 份周报和 1 份月度输出，且只包含 ready 成就。
4. runner 能将 P0 / P1 failure 映射到 persona、周次、源事件和产品能力。
5. 新 Harness 纳入 `make project-gate`，但 persona fixture 的能力差距须以可解释报告呈现。

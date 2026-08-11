# Cockpit 核心闭环收敛与产品减法 Spec

> 日期：2026-08-11
> 状态：待维护者最终审阅后进入实施计划
> 面向执行者：Terra 或其他实现模型
> 性质：产品决策 + 技术行为契约，不是逐行实现计划
> 上位约束：[`.ai/AI_CTO.md`](../../../.ai/AI_CTO.md) · [`docs/GOAL.md`](../../GOAL.md) · [`docs/architecture/ai-native-architecture-v1.md`](../../architecture/ai-native-architecture-v1.md)

## 1. 执行摘要

Cockpit 当前不缺功能，缺的是一条可信、简单、可反复使用的主路径。现状同时向用户暴露看板、聊天、成就库、周报、CV、PR 描述、六种 Agent 接入、质量统计和多种任务完成视图；与此同时，`needs_data` 成就仍可能从聊天周报泄漏到正式输出，补全追问会在 CV 没有吸收新证据时直接升为 `ready`，自动润色路径还会丢失 AI 返回的追问。

本次改造的唯一目标是把产品收敛为：

```text
倒事 / 建任务
    ↓
完成时描述结果
    ↓
AI 生成有证据约束的成就陈述
    ↓
缺证据则补全并重新生成，用户确认
    ↓
成就库（单一数据源）
    ↓
输出中心（周报 / 月报 / 述职 / CV）
```

本次必须同时完成两类工作：

1. **修真实性与安全边界**：数据目录、readiness、追问恢复、ready-only 输出、CoT 移除、加载失败可见。
2. **做产品减法**：删除 PR 描述核心功能、合并 CV 与周报、降级 Agent 接入、删除虚荣质量指标、删除重复完成视图、移除 task draft、收敛 onboarding 与导航。

不允许只做 UI 改名而保留旧数据流，也不允许只修某一个入口。Web、聊天、MCP、模板和存储边界必须一致。

## 2. 成功标准

### 2.1 用户成功标准

- 用户从完成任务到保存成就，正常路径不超过 90 秒。
- 任何进入周报、月报、述职或 CV 的成就都已经过统一 readiness 边界。
- 用户回答追问后，能看到吸收了新证据的新版 CV，并且必须确认后才变为可输出。
- 首页一级导航最多四个目的地：看板、成就库、输出中心、设置。
- 用户不再看到 `ready`、`needs_data`、`pending`、`CoT`、`workspace`、内部版本号等工程术语。
- 断网且无 LLM 时，项目/任务 CRUD、成就查看、草稿保存、本地模板输出、导出备份仍可用。
- 用户可以导出全部职业资产，并能在导入前预览、在导入失败后恢复。

### 2.2 质量成功标准

- 已确认成就的事实编造为 0。
- 所有正式输出入口对非 ready 成就的泄漏为 0。
- 自动建议、手动重新生成、追问恢复、聊天完成和 MCP 完成共用同一 readiness 判定。
- 两周真实自用至少积累 20 条成就，并记录：直接采用、轻改采用、重写、放弃。
- 周报/月报/述职/CV 每类至少生成一份真实输出；每类可直接采用或轻改采用比例达到 70%。
- 完整后端测试、项目质量门和前端类型检查全部通过。

## 3. 非目标

本次不做以下事项：

- 不开发团队协作、共享空间、团队权限或老板视图。
- 不开发云同步、账号、支付、移动端或外部通知。
- 不新增主动联网搜索、邮件、IM、Computer Use。
- 不实现 Refiner Agent、Git 成就候选自动采集或 Personal KG。
- 不删除 `blocked`、项目归档、完成撤销、reflection 或聊天本身。
- 不在本次直接删除 checklist；先记录真实使用，再按第 13 节的退出条件决策。
- 不因为合并页面而丢失已有成就、任务、聊天、追问答案、trace 或 feedback。

## 4. 当前已确认问题与根因

以下问题已经通过代码追踪或隔离数据库复现，执行者不得把它们降级为“可选优化”。

| 编号 | 问题 | 根因 | 风险级别 |
|---|---|---|---|
| P0-1 | 回答完追问后 CV 没变，但状态直接升 `ready` | `storage.answer_follow_ups` 只写答案并改状态，没有重写和确认 CV | P0 事实边界 |
| P0-2 | 聊天生成周报会包含非 ready 成就 | `tool_generate_weekly_report` 查询本周全部成就，没有 `only_ready=True` | P0 输出泄漏 |
| P0-3 | 完成弹窗自动建议丢失 AI 追问 | 自动调用只保存 `cv` 与 trace id，没有保存 `follow_up_questions` | P0 readiness 绕过 |
| P0-4 | 产品重新向前端返回和展示原始 CoT | 流式后端捕获 `cot_blocks` 并在 end 事件返回，前端提供 CoT 开关 | P0 隐私/安全 |
| P0-5 | 数据实际落在项目目录的 `./~/.cockpit/` | 环境变量中的 `~` 被当普通相对路径，缺少 `expanduser()` | P0 数据位置与迁移 |
| P1-1 | 首页数据请求失败时显示“0 条成就”和大片空白 | SWR 没有明确 loading/error 状态，计数对 `undefined` 回退为 0 | P1 误导 |
| P1-2 | 现有质量门全绿但漏掉 P0-1/P0-2 | 多数测试验证源码字符串存在，而不是跨入口真实行为 | P1 测试盲区 |
| P1-3 | 系统 prompt 与实现漂移 | prompt 仍写两态、完成后 task 移走、固定数据路径等旧行为 | P1 Agent 漂移 |
| P1-4 | README/PRD/UI 版本与当前实现不一致 | 功能迭代后文档和用户界面残留内部版本文案 | P1 认知负担 |

## 5. 目标信息架构

### 5.1 一级导航

首页一级导航只保留：

1. **看板**：当前页，不额外显示链接。
2. **成就库**：`/achievements`。
3. **输出中心**：沿用 `/report` 作为主路由，用户文案统一叫“输出中心”。
4. **设置**：`/settings`，主题切换可保留为独立图标。

从首页移除：

- `PR 描述`
- `CV 视图`
- `⚡ AI 直连`、红点、安装数量与 30 秒状态轮询
- 常态 LLM 模型名称、`via LLM`、`via 关键词` 等技术状态；仅在不可用时展示可行动的错误入口

### 5.2 二级入口

- Agent/MCP 接入中心保留，但只能从“设置 → 高级接入”进入。
- `/cv` 保留兼容跳转，不再保留独立产品页。
- `/pr` 删除，不提供新的核心入口。
- `/achievements/follow-up` 可以保留路由，但产品文案改为“补全证据”，并按第 7 节重做行为。

### 5.3 首页内容

首页按以下顺序展示：

1. 资产摘要：累计可用成就数、待补证据数；加载中不能显示假 0。
2. 今日聚焦：程序按确定性规则给出的少量任务。
3. 项目与未完成任务。
4. 今日新沉淀：仅在当天有数据时显示，最多 3 条，更多跳成就库。

首页删除：

- “今日承诺”星标、localStorage 承诺集合、进度条、`挑 3 个任务`引导。
- 全局“已完成任务”折叠区。
- 项目卡里的“7 天内成就”重复视图。
- 任何以“今日完成数”为核心的游戏化反馈。

完成后的资产以 Achievement 为单一用户可见来源；Task 仍在数据库保留，以支持撤销与审计。

## 6. 统一成就 Readiness 契约

### 6.1 状态语义

数据库继续保留三态，但 UI 使用人话：

| 内部状态 | 用户文案 | 能否进入正式输出 |
|---|---|---|
| `ready` | 可直接使用 | 是 |
| `needs_data` | 待补证据 | 否 |
| `pending` | 草稿 | 否 |

状态是程序根据证据推导的输出资格，不是让用户手动设置的普通字段。

### 6.2 唯一写入边界

所有完成与补证入口必须调用同一个存储层 readiness 函数。禁止 Web、聊天或 MCP 自己决定最终状态。

`ready` 至少要求：

- outcome 去空白后不少于 10 个字符；
- CV 不是 `完成「<任务标题>」` 兜底；
- 所有非空追问都有非空答案；
- CV 已吸收本轮补充证据，而不是保存追问前的旧文本；
- 确定性 provenance guardrail 没有发现用户输入中不存在的数字、实体或 ownership 升级；
- 用户确认了最终 CV。

任一条件不满足：

- 用户显式选择“暂存草稿”时为 `pending`；
- 其他情况为 `needs_data`。

### 6.3 输出读取边界

正式输出不得由各页面自行散落过滤。建立一个明确的共享查询接口，例如：

```python
storage.list_output_ready_achievements(
    *, since: date | None, until: date | None, project_id: str | None
) -> list[Achievement]
```

或保留 `list_achievements(only_ready=True)`，但所有正式输出必须显式使用，并有跨入口行为测试。正式输出包括：

- 输出中心全部模板；
- 聊天 `generate_weekly_report`；
- 未来 Composer；
- 任何下载、复制或导出“周报/述职/CV”的路径。

成就库和补证队列仍可读取非 ready 内容；它们不是正式输出。

### 6.4 聊天周报修正

- `tool_generate_weekly_report` 只读取 ready 成就。
- bullet 优先使用 `cv`，不能优先使用未经整理的 `outcome`。
- 没有 ready 成就时，返回“本周暂无可直接使用的成就；有 N 条待补证据”，并给出补证入口，不得把待补内容塞进周报。
- 聊天和输出中心必须调用同一模板/Composer 核心，不能维护两套拼装逻辑。

## 7. 完成沉淀与补证恢复

### 7.1 完成弹窗目标形态

主流程只保留：

1. 结果描述（唯一主输入）。
2. AI 建议的成就陈述，可编辑。
3. 缺失信息追问，必要时出现。
4. “沉淀成就”主按钮。
5. “暂存草稿”次按钮。
6. reflection 继续放在可选折叠区。

删除：

- `ready / needs_data / pending` 三态选择器。
- “自动建议”和“手动润色”两套并行概念。
- 把问题文本追加进 outcome 的交互。
- “重置为完成「标题」”作为鼓励动作；兜底只能是降级展示，不是推荐结果。

### 7.2 AI 建议流程

- outcome 停笔后自动请求一次建议，现有 1.5 秒防抖可保留。
- 同一请求必须处理并保存：`cv`、`follow_up_questions`、`trace_id`、guardrail 结果。
- 用户继续编辑 outcome 后，旧建议标记为过期；再次防抖生成，禁止并发旧响应覆盖新响应。
- 手动入口改名为“重新生成”，只在已有建议或自动请求失败时出现。
- LLM 不可用时显示可编辑兜底，但保存结果必须进入“待补证据”，不能 ready。
- 自动请求失败不能静默伪装成功；主完成流程仍可继续保存草稿或待补证据。

### 7.3 追问交互

- 每个问题有独立答案输入框，答案保持结构化，不拼进 outcome 字符串。
- 用户可以保存部分答案，状态保持“待补证据”。
- 所有问题答完后，系统基于 task、project、outcome、reflection、问题与答案重新生成 CV。
- 新 CV 必须作为候选展示；用户确认或编辑后才提交最终 resolve。

### 7.4 Resolve API 与事务

保留当前补全 API 作为“保存答案草稿”时，它不得自动升级 ready。新增或重构为一个原子 resolve 边界：

```text
POST /api/achievements/{id}/resolve
body:
  answers: Record<string, string>
  cv: string
  distillation_trace_id?: string

行为:
  - 在一个事务中保存答案和最终 CV
  - 运行统一 readiness + provenance 判定
  - 只有全部条件满足才写 ready
  - 返回最终状态与未满足原因
```

用于生成新版 CV 的 LLM 请求必须能接收结构化追问答案。可以扩展 `polish_cv` 输入，也可以建立职责更清晰的 refinement 端点，但不能把答案拼成不可审计的自由文本后丢失来源。

### 7.5 反馈闭环

- 自动/重新生成得到的候选 CV 与用户最终保存的 CV 必须关联到同一个 trace。
- 在首次完成时就记录 candidate → final 的反馈，不只在成就库后续编辑时记录。
- 记录本地、非云端的采用标签：直接采用、轻改、重写、暂存/放弃。
- 这些数据只用于两周 dogfooding 与 Harness，不在 UI 做增长型统计。

### 7.6 Web、聊天与 MCP 的入口一致性

三个入口可以有不同交互，但不能有不同事实边界：

- **Web**：完成弹窗展示候选 CV 和追问；用户确认最终 CV 后调用统一完成/resolve 边界。
- **聊天**：用户说“完成了”后，Agent 先收集 outcome，再展示候选 CV 与必要追问；必须得到用户对最终 CV 的明确确认才能写为 ready。用户选择“先记下来”时只能保存为 needs_data 或 pending，不能在生成文案后静默完成。
- **MCP**：`complete_task` 必须使用同一存储层判定；调用方传入的 `cv_status=ready` 不能绕过证据、追问、provenance 与确认要求。工具响应必须返回存储层实际状态和未满足原因，便于上游 Agent 继续补证。

三入口都必须保留来源审计信息（Web/chat/MCP）和关联 trace，但来源只用于诊断，不能改变 readiness 规则。

### 7.7 落库结果驱动 UI

- 完成 API 必须返回实际落库后的 Achievement，包括最终状态和未满足原因。
- 首页完成回调必须使用这个响应更新缓存，禁止无条件把“可直接使用”数量 `+1`。
- toast 按实际结果显示“已沉淀，可直接使用”“已保存，待补证据”或“已暂存草稿”，不得统一宣称 ready。
- snapshot 必须分别返回 `achievementsReady`、`achievementsNeedsData`、`achievementsPending`，或额外提供语义明确的 `achievementsNeedsAttention = needs_data + pending`。
- 首页“待补”不得只统计 pending；如果产品分别展示“待补证据”和“草稿”，两者必须各自按真实状态计数。
- snapshot 尚未成功返回时，计数展示骨架或加载状态，不能用 0 代替未知。

## 8. CoT 完全移除

CoT 不是高级选项，而是禁止进入产品数据面的内部内容。

必须删除：

- `app/llm/chat_engine.py` 对完整 think 块的捕获与 `cot` 事件；保留 strip/sanitize 防线。
- `app/api/chat.py` 的 `cot_blocks` 累积与 SSE end 字段。
- `web/lib/hooks/useChatStream.ts` 的 `cotBlocks` 状态。
- `web/components/ChatWindow.tsx` 的开关、localStorage key、`CotBlock` 和相关图标/文案。
- 所有鼓励展示“AI 思维链”的测试。

必须保留并强化：

- 每个 LLM 输出入口的 think/reasoning 标签剥离。
- markdown fallback 在清洗后文本上执行。
- 测试断言 SSE、持久化消息、DOM 和 tool fallback 均不含 CoT 原文。

## 9. 本地数据目录、迁移与可携带性

### 9.1 路径修正

- `COCKPIT_DATA_DIR` 进入系统后必须 `expanduser()`，再规范化为绝对路径。
- `.env.example` 不应把未经验证的 `~/.cockpit` 作为会被直接解析的普通字符串；可以删除该配置让安全默认值生效，或保证 validator 展开。
- README、设置页和日志展示的路径必须来自同一个 resolved setting。

### 9.2 错位数据库迁移

启动时检测历史错误位置 `<cwd>/~/.cockpit/cockpit.db`：

1. **只有错误位置存在**：原子复制到正确用户目录；校验大小/哈希和可打开性；保留原文件为带时间戳备份，不删除。
2. **正确位置和错误位置都存在且内容相同**：使用正确位置；保留旧文件，不自动删。
3. **两处都存在且内容不同**：禁止静默覆盖或自动合并。应用进入明确的“发现两份数据”恢复状态，暂停写入，要求用户选择主库；选择前两份都保持不变。
4. 任意迁移失败：继续保护原库，显示可行动错误，不创建一个空库伪装成功。

迁移逻辑必须有隔离临时目录测试，不能在测试中接触真实 `~/.cockpit`。

### 9.3 导出

设置页新增“数据与备份”：

- 导出一个带 `schema_version` 与生成时间的 JSON 或 zip 包。
- 至少包含 projects、tasks、achievements、follow-up questions/answers、chat sessions/messages、distillation traces/feedback。
- 不导出明文 API key、加密密钥或环境变量。
- 导出不依赖 LLM 或网络。

### 9.4 导入

- 先解析并校验 manifest/schema，不直接覆盖。
- 展示预览：项目、任务、成就、聊天条数，冲突数量与将采取的策略。
- 用户明确确认后执行。
- 导入前自动备份当前数据库。
- 使用事务；失败则回滚，并保留导入前备份。
- 第一版只支持 cockpit 自身导出格式，不做 Notion/Todoist 导入。

## 10. 产品减法

### 10.1 删除 PR 描述功能

从核心仓库删除：

- `/pr` 页面与导航入口；
- `web/lib/pr.ts`；
- `api.generatePr`；
- `/api/llm/generate_pr` schema、prompt、fallback 与处理函数；
- 成就库中的 PR 候选选择和 `cockpit_pr_candidates` localStorage；
- 只为 PR 功能存在的测试、图标和文案。

理由：PR 描述应该由代码 diff/commit 在提交前生成，而 Achievement 是完成后的职业资产。把两者绑在一起既缩窄目标用户，又存在时间顺序错位。

历史 changelog/lesson 不删除，只新增一条“功能退出”记录，说明被推翻原因。

### 10.2 合并 CV 与输出中心

- `/report` 保留路由，标题改为“输出中心”。
- `/cv` 改为兼容跳转：`/report?type=cv&range=all`，不得继续维护独立业务逻辑。
- 删除独立 CV 页面与重复数据拼装代码；可复用的纯模板逻辑迁入统一 Composer。
- 首页只显示“输出中心”一个入口。

输出中心支持四种输出类型：

1. 周报
2. 月报
3. 季度/年度述职
4. CV 成就清单

周报可保留“产品/研发”样式，但它们是周报内部样式，不再与输出类型混成同一级概念。

### 10.3 统一 Composer 输入

统一 Composer 至少接收：

- 指定时间窗内的 ready achievements：本期成果；
- 未完成 tasks：下期计划候选；
- blocked tasks：风险/阻塞；
- 项目名称与描述：分组上下文。

确定性模板负责筛选和排版；LLM 润色属于可选增强，不能改变事实、扩大 ownership 或编造数字。

不同输出的最低结构：

| 输出 | 时间窗 | 内容 |
|---|---|---|
| 周报 | 本周/上周 | 已完成、风险阻塞、下周计划 |
| 月报 | 本月/上月 | 关键成果、项目进展、问题与下月重点 |
| 述职 | 季度/年度/自定义 | 核心成果、角色与行动、证据、复盘 |
| CV | 1/2/3 年或全部 | 按项目/主题分组的 ready 成就 |

复制、下载和编辑能力保留。所有模板必须在无 LLM 时可生成。

### 10.4 降级 Agent 接入

- MCP server 和 `/integrations` 页面可以保留。
- 首页删除链接、红点、安装数量和轮询。
- 设置页“高级接入”提供入口，并明确这是可选采集通道。
- 不鼓励安装全部 Agent；已安装 1 个即不应提示缺少另外 5 个。
- 接入页不再使用“杀手功能”等内部营销逻辑。

### 10.5 删除虚荣质量统计

删除用户可见的：

- 量化率
- 强动词比例
- 动词分布
- “优秀/良好/一般/待提升”评分
- 页面上的 `v0.3.5 / v0.4.3` 等内部版本号

相关 `achievement-stats.ts` 与脚本测试如果没有其他消费者，应删除。

成就库改为事实健康视图：

- 可直接使用 N 条
- 待补证据 N 条
- 草稿 N 条
- 每条待补项明确显示原因：缺结果、缺影响、追问未答、CV 尚未吸收证据等

量化数据仍可作为一种证据类型被追问，但不能成为所有岗位的统一评分，也不能推动用户编造数字。

### 10.6 删除 task draft

`Task.draft` 已不再符合“新任务直接落地”的现行流程。本次完整删除：

- Pydantic 与 ORM 字段；
- Task API 字段；
- `confirm_drafts` API、tool 和 prompt；
- 状态菜单里的草稿 toggle；
- MCP 返回中的 draft；
- 相关测试与文案。

迁移规则：历史 `draft=true` 任务直接作为普通未完成任务保留，不删除、不完成、不改标题或项目；删除列前先做数据库备份。

### 10.7 Tags 的处理

Achievement tags 当前没有写入入口，也没有形成输出价值。

- UI、API DTO 和新功能不再展示或依赖 tags。
- 为兼容可能存在的历史导入数据，本次不物理删除数据库 `tags_json` 列；导出/导入必须原样保留。
- 标记为 deprecated，后续只有在真实用户需要筛选时才重新设计，不允许继续添加半成品入口。

### 10.8 Onboarding 收敛

删除首次访问 1 秒后弹出的三步 modal，改为首页空状态内联引导：

1. 倒入一件正在做的事。
2. 完成时写下结果并沉淀。
3. 有成就后去输出中心生成周报。

要求：

- 不遮挡页面，不依赖 localStorage 才能看懂核心路径。
- CTA 可以展开聊天并聚焦输入，也可以使用看板的新建项目/任务入口。
- 删除“跳过后又说下次还会问”的矛盾 toast。
- 设置页不再需要“重看三步弹窗”；可提供静态“快速开始”链接。

### 10.9 项目删除降级为高级危险操作

- 常用看板和项目卡移除“永久删除”入口，归档作为默认退出方式。
- 永久删除只允许从“设置 → 数据与备份/已归档项目 → 危险操作”进入。
- 确认界面必须展示将删除的任务、成就及关联数据数量，并要求输入完整项目名；普通的二次点击不够。
- 执行前创建可恢复备份，并记录本地审计信息。
- 后端 `delete_project` 的确认与级联保护不能因为入口降级而移除；聊天中的删除仍需先查找项目、解释影响并取得明确确认。
- 若现有 schema 会级联删除 Achievement，实施前必须先确认这符合数据资产原则；默认方案应优先禁止删除含成就的项目，或将成就迁入“未归属/已删除项目”而不是销毁职业资产。

## 11. 加载、错误与非技术文案

### 11.1 数据状态

每个核心页面必须区分：

- 正在加载
- 成功但为空
- 后端不可达
- 数据库迁移/冲突等待处理
- LLM 不可用但本地功能可继续

禁止用 `snapshot?.count ?? 0` 在尚未加载或加载失败时显示假 0。错误状态必须有“重试”和“打开设置/查看数据位置”的行动入口。

### 11.2 用户文案

用户界面统一替换：

- `ready` → 可直接使用
- `needs_data` → 待补证据
- `pending` → 草稿
- `workspace` → 输出中心
- `CV` 可在行业语境下保留，但首处说明“简历成就”
- 删除 `CoT`、session id、模型内部路径、版本号、`via LLM` 等实现细节

技术信息保留在设置诊断区和日志，不放在日常主路径。

## 12. 文档与 Prompt 对齐

必须更新：

- `app/llm/prompts/cockpit_system.md`
- `README.md`
- `docs/PRD.md`
- `docs/GOAL.md` 中受本次退出/合并影响的现状描述
- `AGENTS.md` 的测试基线和产品入口说明
- `docs/changelog/README.md` 与本次 changelog
- 受影响 lessons 的推翻链索引

Prompt 至少修正：

- 三态状态语义与统一 readiness 边界；
- 完成后的 Task 仍保留，Achievement 追加；
- 聊天正式输出只读 ready 成就；
- 数据路径来自 resolved settings，不硬编码未经展开的字符串；
- 删除 PR 描述能力与 `confirm_drafts`；
- 不鼓励“必须强动词、必须量化”，事实来源永远优先；
- AI 不得向用户暴露思维链。

README/PRD 至少修正：

- 当前版本、测试数量和真实页面；
- 删除已退出的 PR 描述产品能力；
- 把 CV 并入输出中心；
- 说明本地导出/导入；
- 删除与宪法冲突或已不计划实施的旧路线描述。

历史 changelog 和 lesson 文件是演化记录，不覆盖或删除。新增“为什么退出/合并”的记录，并在索引上标明推翻链。

## 13. 暂时保留与两周退出门槛

以下功能本次保留：

- `blocked`：与 priority 是不同维度，直接服务风险输出。
- 项目归档与恢复：满足可逆原则。
- 完成撤销：防止误沉淀，且 Task 保留让恢复无损。
- reflection：继续可选，不强迫。
- checklist：暂不删除。
- 多聊天 session：暂不删除，但不再在主界面展示 session id。
- MCP server：保留为可选授权采集通道。

两周 dogfooding 后，按真实使用决定 checklist 和多 session 是否继续保留：

- 20 条真实成就周期内从未使用 checklist → 提出删除 RFC；
- 20 条真实成就周期内没有切换过历史 session → 简化为单一连续对话，并保留历史导出；
- 有明确真实场景则保留，并补上使用路径测试。

不能因为当前本地样本少就立即删除这两项；也不能在没有使用证据时继续扩展它们。

## 14. 兼容性与迁移

### 14.1 路由

- `/report`：保留，产品标题改为输出中心。
- `/cv`：服务端或客户端兼容跳转到 `/report?type=cv&range=all`。
- `/pr`：删除。若静态部署无法优雅返回 410，可返回 404；不得继续挂在导航或保留空壳页面。
- `/integrations`：保留，从设置进入。
- `/achievements/follow-up`：保留并重做。

### 14.2 API

- 删除仅供 PR 描述使用的 LLM API。
- 删除 task draft/confirm APIs 与 tools。
- 现有 achievements list 保持兼容；正式输出新代码必须使用 ready-only 共享查询。
- 现有 follow-up patch 改为保存答案但不自动 ready；新增原子 resolve 边界。
- MCP 的 `complete_task` 可以保留 `cv_status` 输入以兼容旧客户端，但存储层忽略其 ready 声明并自行推导；下一版再考虑从 schema 移除。

### 14.3 数据库

- 任何 schema 迁移前创建可恢复备份。
- 删除 task draft 列时保留全部 task 行。
- `tags_json` 本次不删除。
- 不修改 Achievement id、Task id、Project id 或历史日期。
- 不删除现有聊天、trace、feedback、follow-up answers。
- 迁移脚本必须幂等；应用多次启动不能重复复制、重复删列或覆盖备份。

### 14.4 localStorage

停止读取并可清理：

- 今日承诺 key
- PR candidates key
- CoT 显示 key
- onboarding modal key

旧 key 遗留不得导致异常；不需要专门迁移用户数据，因为这些 key 不属于职业资产。

## 15. 测试与质量门

### 15.1 必须新增的行为测试

#### Readiness

- 自动建议返回 questions 时，完成保存不能 ready。
- 手动重新生成和自动建议对 questions 的处理一致。
- 部分回答追问后仍为 needs_data。
- 全部回答但未重新生成/确认 CV 时仍为 needs_data。
- 全部回答 + 新 CV + 用户确认 + guardrail 通过后才 ready。
- 新 CV 含无来源数字、实体或 ownership 升级时不能 ready。
- Web、聊天、MCP 对同一组输入得到相同最终状态；调用方声明 ready 不能绕过存储层。
- 完成响应、首页计数和 toast 使用实际落库状态，不做乐观 `ready + 1`。

#### 输出

- 同一隔离 DB 同时放 ready、needs_data、pending 三条 sentinel。
- 输出中心四种模板、聊天周报都只能出现 ready sentinel。
- 非 ready sentinel 不得出现在复制、下载和最终 markdown。
- 没有 ready 时返回正确空状态和待补数量。

#### CoT

- 模型流式返回跨 chunk `<think>` 时，用户文本正常、SSE 无 cot 字段、DOM 无原文、持久化无原文。
- CoT 中的伪工具调用不得执行。

#### 数据目录

- `~/...` 正确展开。
- 只存在错位 DB 时安全复制并保留备份。
- 两个不同 DB 时进入冲突状态且无写入。
- 迁移重复运行幂等。

#### 数据导入导出

- round-trip 后核心表数据一致。
- API key 不出现在导出包。
- 损坏包、未知 schema、冲突预览和事务回滚都有测试。

#### 产品减法

- 首页不再存在 `/pr`、`/cv`、AI 直连红点、CoT、承诺进度和内部版本号。
- `/cv` 正确跳到输出中心 CV 模板。
- 设置页能进入高级接入。
- onboarding 不再渲染遮罩 modal。
- task API/MCP 不再暴露 draft 新行为。
- 常用看板不再提供永久删除项目；高级删除要求项目名、影响摘要与备份。
- snapshot 的“待补”语义覆盖 needs_data 与 pending，加载/失败时不显示假 0。

### 15.2 现有测试处理原则

- 删除只为被删除功能背书的静态 invariant 测试。
- 历史 lesson/changelog 的文本不因功能删除而改写。
- 把“源码中包含某字符串”的关键宪法测试替换为实际函数/API 行为测试。
- Project Gate 的 `report_composition` 不能只跑页面静态测试，必须运行 ready-only 跨入口测试。
- `constitution` suite 必须覆盖 CoT 不泄露和所有正式输出 ready-only。

### 15.3 最终验证命令

执行者完成实现后至少运行：

```bash
make clean
.venv312/bin/pytest app/tests/ -q
cd web && npx tsc --noEmit
cd .. && make project-gate
```

遵守项目 lesson：不要在正在运行的 dev server 上执行 `next build`。

## 16. 建议实施顺序

本 Spec 应拆成独立实施计划，按以下顺序执行，不能从视觉减法先开始：

### Phase 1：真实性与数据安全

1. 数据路径展开与错位 DB 迁移。
2. follow-up 不再自动 ready。
3. 自动建议透传 questions。
4. 原子 resolve + 最终 CV 确认。
5. 所有正式输出 ready-only。
6. CoT 完全移除。
7. 加载/错误状态。

### Phase 2：产品减法

1. 删除 PR 描述全链路。
2. 删除 task draft 全链路并迁移。
3. 合并 CV 到输出中心。
4. 降级 Agent 接入。
5. 删除承诺进度、重复完成视图和虚荣质量指标。
6. onboarding 改内联。
7. 项目永久删除降级到高级危险操作。
8. 用户文案去工程化。

### Phase 3：统一输出与可携带性

1. 统一 Composer。
2. 补齐周报风险/下周计划、月报、述职、CV。
3. 设置页导出/导入与恢复。
4. 本地采用反馈闭环。

### Phase 4：文档、回归与 dogfooding

1. Prompt/README/PRD/GOAL/AGENTS 对齐。
2. 更新 changelog 与推翻链。
3. 完整回归与 Project Gate。
4. 两周、20 条真实成就 dogfooding。
5. 根据真实使用决定 checklist 与多 session 去留。

## 17. 预计受影响文件

实现前仍需用 `rg` 做完整引用搜索。至少包括：

### 后端

- `app/core/config.py`
- `app/core/models.py`
- `app/core/storage.py`
- `app/core/focus.py`
- `app/api/achievements.py`
- `app/api/tasks.py`
- `app/api/chat.py`
- `app/api/llm.py`
- `app/api/reminders.py`
- `app/llm/chat_engine.py`
- `app/llm/tools.py`
- `app/llm/prompts/cockpit_system.md`
- `app/mcp_server.py`

### 前端

- `web/components/MainBoard.tsx`
- `web/components/CompleteTaskModal.tsx`
- `web/components/ChatWindow.tsx`
- `web/components/OnboardingTooltip.tsx`
- `web/components/FollowUpReminder.tsx`
- `web/lib/hooks/useChatStream.ts`
- `web/lib/api.ts`
- `web/lib/templates.ts`
- `web/lib/cv-template.ts`
- `web/lib/pr.ts`
- `web/lib/achievement-stats.ts`
- `web/lib/commitments.ts`
- `web/app/achievements/page.tsx`
- `web/app/achievements/follow-up/page.tsx`
- `web/app/report/page.tsx`
- `web/app/cv/page.tsx`
- `web/app/pr/page.tsx`
- `web/app/integrations/page.tsx`
- `web/app/settings/page.tsx`

### 测试、脚本与文档

- `app/tests/constitution/`
- `app/tests/test_api_answer_follow_ups.py`
- `app/tests/test_api_complete_task.py`
- `app/tests/test_complete_modal_minimal_invariants.py`
- `app/tests/test_complete_path_invariants.py`
- `app/tests/test_report_workspace_invariants.py`
- `app/tests/test_stream_chat.py`
- `app/tests/test_integrations.py`
- `app/tests/test_mcp_server.py`
- `app/tests/test_storage.py`
- `app/tests/harness/`
- `docs/harness/capabilities-v1.yaml`
- `README.md`
- `docs/PRD.md`
- `docs/GOAL.md`
- `AGENTS.md`
- `docs/changelog/`
- `docs/lessons/`

被删除或合并文件必须先确认没有其他运行时消费者；历史文档中的文件名引用作为演化记录可以保留，但索引必须标明已退出。

## 18. Definition of Done

只有同时满足以下条件，本改造才算完成：

- P0-1 至 P0-5 都有先失败后通过的回归测试。
- 回答追问后必须经过“重新生成 → 用户确认”，旧 CV 不可能直接 ready。
- Web 输出中心和聊天周报对非 ready 内容零泄漏。
- 前后端、SSE、持久化和 DOM 均不再包含可展示 CoT 的通道。
- resolved 数据目录正确，错位 DB 有安全迁移与冲突处理。
- `/pr` 全链路退出；`/cv` 只做兼容跳转；首页只有一个输出入口。
- Agent 接入从首页降级到设置高级项，无红点催促。
- 成就库不再显示量化率、强动词率或动词分布。
- 今日承诺、全局已完成任务和项目内 7 日成就重复视图已删除。
- task draft 全链路删除且历史 task 无损。
- tags 不再出现在产品逻辑中，但历史 tags 数据仍可导出/导入。
- onboarding 为内联空状态，不再弹遮罩 modal。
- 项目卡和常用看板只提供归档；永久删除位于高级危险操作并具备备份与强确认。
- 输出中心支持周报、月报、述职、CV，且断网可生成。
- 设置页支持安全导出、预览导入、自动备份和失败回滚。
- 所有用户文案去除内部状态名、CoT、workspace 和版本号。
- Prompt、README、PRD、GOAL、AGENTS、changelog 与代码一致。
- 完整测试、类型检查和 Project Gate 通过。
- 真实 dogfooding 结果单独记录，合成 Harness 不冒充真实用户验证。

## 19. 执行者约束

- 开工前必须重新阅读 `.ai/AI_CTO.md`、`docs/GOAL.md`、相关 architecture/harness 和 lessons。
- 必须先把本 Spec 拆成可审阅的 implementation plan，再写代码。
- 每个 P0 修复先写失败测试；不能用放宽 guardrail 换表面成功率。
- 不允许为了删页面直接删除用户数据库字段或历史记录。
- 不允许修改或覆盖维护者已有的未提交文件。
- 每个 Phase 独立验证，避免一次提交同时混入安全修复、schema 迁移和大规模 UI 删除。
- 发现本 Spec 与宪法冲突时，以宪法为准并暂停实施，提交决策问题，不自行扩 scope。

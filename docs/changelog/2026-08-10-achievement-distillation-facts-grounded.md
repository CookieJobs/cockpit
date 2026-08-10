# 2026-08-10 — Achievement Distillation 事实优先校准

## 状态

**现行**：`polish_cv_facts_grounded_v1`。

## 背景

首轮 Achievement Distillation Harness 显示：许多失败不是模型完全没有生成，而是 prompt 鼓励它把表达“写强”。模型因此把“参与”升级为“主导”，或从前后数值自行计算百分比/倍数；既有 P0 provenance guardrail 随后拒绝该输出，用户最终得到通用 fallback。

这不是应当放宽 guardrail 的信号。Harness-first 决策是降低生成阶段的越界倾向，同时保留原有运行时安全边界。

## 选择

比较过三条路径：

1. **事实约束 prompt（采用）**：明确 ownership 只能复用原文、数字不得推导或新造、事实充分时不重复追问。
2. 输出后 scrub/rewrite：拒绝。它会掩盖生成错误，且规则容易破坏语义。
3. 先抽取结构化事实、再生成：保留为下一阶段候选，但当前复杂度不匹配最小实验。

## 改动

- `app/api/llm.py`：以事实优先的 few-shot 替换会诱导编造数字、用户量或 ownership 的示例；更新 trace prompt version。
- `app/tests/test_api_polish_cv_v0304.py`：锁住 ownership、数字来源和“不重复追问”的 prompt 不变量。

## Harness 验证

| 运行 | Current Capability | Fallback | P0 safety |
|---|---:|---:|---:|
| 校准后的固定输出基线 | 13/19（68.4%） | 16.7% | 0% |
| v0.3.5 production L1 实跑 | 16/19（84.2%） | 5.3% | 0% |
| v0.3.5 production + minimal L2 实跑 | 13/19（68.4%） | 0% | 0% |

两次 live run 含 LLM 随机性，不能将差异视为严格的因果 A/B；但候选和 production 均使用同一 P0 guardrail，未通过放宽安全约束换取提升。后续应采用固定模型版本、重复采样或 paired run 再把分数作为 release gate。

## 未解决项

- 参与型 / 信息稀疏输入的追问信息增益仍不足。
- Generic fallback 与 outcome 重复仍影响 Resume Usefulness。
- Minimal semantic judge 与被测系统共享 configured LLM client，需独立 judge 或人工抽样校准。

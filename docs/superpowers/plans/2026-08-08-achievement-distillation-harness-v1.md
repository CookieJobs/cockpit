# Achievement Distillation Harness v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有 `polish_cv` 能力建立可重复评测、运行时质量检查、版本追踪和回归门禁，而不重写当前生成器或完成任务流程。

**Architecture:** Harness 作为 `app/llm` 之外的独立评测边界，使用一个适配器调用现有 `polish_cv` 生成逻辑，再由确定性 L1 evaluator 计算硬约束结果。离线 runner 输出 JSON/JSONL 报告；线上调用只增加轻量 trace 和 guardrail 结果记录。LLM Judge 与用户 diff 反馈作为后续增量，不进入第一批阻塞实现。

**Tech Stack:** Python 3.11；pytest；Pydantic v2（沿用项目现有模型）；JSON/JSONL；SQLite（沿用现有 storage）；FastAPI 现有 `polish_cv` 端点。

## Global Constraints

- 不重写 `app/api/llm.py` 的生成 prompt；第一阶段只包裹、记录和评测现有生成器。
- 不新增第三方依赖；优先使用 Python 标准库、Pydantic 和项目现有测试工具。
- Truthfulness 是不可抵消的 P0 约束：未提供数字或实体出现在 CV 中时直接失败。
- fallback 文本 `完成「title」` 不得被记录为真实 `polished` 生成。
- 业务 `cv_status` 与 Harness 的 `generator_status` / `quality_status` 分开记录。
- 评测 dataset 首版固定为 30 条：Golden 10、Boundary 12、Adversarial 8。
- CI 回归命令必须可以在无 LLM API key 的环境下运行；生成器调用使用可注入 fake adapter。
- 修改 Python 后按项目约定清理 `app/llm/__pycache__`；回归使用 pytest 与 `npx tsc --noEmit`，不运行 `next build`。

---

## Task 1: 建立 Harness 内部契约与 30 条评测集

**Files:**
- Create: `app/harness/__init__.py`
- Create: `app/harness/models.py`
- Create: `app/harness/datasets/achievement_distillation_v1.json`
- Create: `app/tests/harness/test_models_and_dataset.py`

**Interfaces:**
- Produces `AchievementDistillationInput`, `AchievementDistillationOutput`, `HardChecks`, `EvaluationResult` 和 dataset loader，供后续 evaluator、runner 使用。
- `AchievementDistillationInput` 字段：`task_title: str`、`task_description: str | None`、`project_name: str | None`、`project_goal: str | None`、`outcome: str`、`reflection: str | None`、`language: str`。
- `AchievementDistillationOutput` 字段：`cv: str`、`follow_up_questions: list[str]`、`generator_status: Literal["polished", "fallback", "parse_failed"]`。
- 每个 case 字段：`id: str`、`category: Literal["golden", "boundary", "adversarial"]`、`input: AchievementDistillationInput`、`expected: dict`、`forbidden: list[str]`、`severity: Literal["p0", "p1"]`。

- [ ] **Step 1: Write failing model and dataset tests**

```python
def test_dataset_has_expected_case_counts():
    cases = load_cases()
    assert len(cases) == 30
    assert sum(c.category == "golden" for c in cases) == 10
    assert sum(c.category == "boundary" for c in cases) == 12
    assert sum(c.category == "adversarial" for c in cases) == 8


def test_input_requires_title_and_outcome():
    with pytest.raises(ValidationError):
        AchievementDistillationInput(task_title="", outcome="", language="zh")


def test_case_contains_expected_and_forbidden_behavior():
    case = next(c for c in load_cases() if c.id == "boundary_participation")
    assert case.expected["action"] == "参与"
    assert "主导" in case.forbidden
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_models_and_dataset.py -v`

Expected: FAIL because the harness package, models, loader, and dataset do not exist.

- [ ] **Step 3: Implement the models, loader, and dataset**

Use Pydantic validation for required strings and literal enums. Keep dataset loading deterministic: read the JSON file relative to the module path, validate every case into the Pydantic model, and raise a clear `ValueError` naming the case id when a case is malformed.

The 30 cases must cover numeric before/after evidence, missing metrics and vague quantifiers, weak wording, participation versus ownership boundaries, repeated CV/outcome, unsupported numbers/entities, and prompt-injection-style adversarial inputs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest app/tests/harness/test_models_and_dataset.py -v`

Expected: all model and dataset tests PASS.

- [ ] **Step 5: Commit the self-contained dataset contract**

```bash
git add app/harness app/tests/harness/test_models_and_dataset.py
git commit -m "test: add achievement distillation harness dataset"
```

## Task 2: Implement deterministic L1 evaluator

**Files:**
- Create: `app/harness/l1.py`
- Create: `app/tests/harness/test_l1_evaluator.py`
- Modify: `app/harness/models.py` only if an evaluator result field needs a precise type correction

**Interfaces:**
- Produces `evaluate_l1(case: EvaluationCase, output: AchievementDistillationOutput) -> HardChecks`.
- Produces `is_l1_pass(hard_checks: HardChecks) -> bool`.
- Numeric checks return the exact unsupported tokens found, not only a boolean, so reports can explain failures.

- [ ] **Step 1: Write failing tests for P0 rules**

```python
def test_unsupported_number_fails():
    case = make_case(outcome="优化登录流程", expected={})
    output = make_output(cv="优化登录流程，成功率提升 30%")
    checks = evaluate_l1(case, output)
    assert checks.has_unsupported_number is True
    assert checks.unsupported_numbers == ["30%"]
    assert is_l1_pass(checks) is False


def test_participation_must_not_be_upgraded_to_leadership():
    case = make_case(outcome="我参与了推荐系统优化", expected={})
    output = make_output(cv="主导推荐系统优化")
    checks = evaluate_l1(case, output)
    assert checks.likely_overclaim is True
    assert checks.ownership_violation is True


def test_valid_number_and_length_pass():
    case = make_case(outcome="耗时从 2 秒降到 0.5 秒", expected={})
    output = make_output(cv="优化登录流程，耗时从 2 秒降到 0.5 秒")
    checks = evaluate_l1(case, output)
    assert checks.has_unsupported_number is False
    assert checks.length_valid is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_l1_evaluator.py -v`

Expected: FAIL because `evaluate_l1` and the detailed hard-check fields do not exist.

- [ ] **Step 3: Implement minimal deterministic checks**

Implement these checks without an LLM:

1. non-empty CV and maximum 80 characters;
2. follow-up count no greater than 3;
3. fallback and parse failure status classification;
4. extraction of Arabic numerals, percentages, decimals, and common Chinese quantity expressions;
5. every output number must occur in `outcome` or task context;
6. ownership comparison for `参与/协助/负责/主导/独立` where a stronger output verb than the input implies a violation;
7. obvious unsupported entities using named tokens present in CV but absent from all input text;
8. normalized character n-gram or `SequenceMatcher` similarity for CV/outcome duplication;
9. strong-action check using the project’s existing strong/weak verb vocabulary.

Do not attempt general entity recognition or semantic truth verification in L1. Mark uncertain cases for L2 rather than inventing a deterministic answer.

- [ ] **Step 4: Run targeted and full harness tests**

Run: `pytest app/tests/harness/test_l1_evaluator.py -v`

Expected: all P0 and boundary rule tests PASS.

- [ ] **Step 5: Commit the L1 evaluator**

```bash
git add app/harness/l1.py app/tests/harness/test_l1_evaluator.py app/harness/models.py
git commit -m "feat: add achievement distillation l1 evaluator"
```

## Task 3: Add generator adapter and offline runner

**Files:**
- Create: `app/harness/adapter.py`
- Create: `app/harness/runner.py`
- Create: `app/harness/report.py`
- Create: `app/tests/harness/test_runner.py`
- Create: `app/tests/harness/test_report.py`
- Create: `app/scripts/run_achievement_harness.py`

**Interfaces:**
- `DistillationAdapter` protocol: `async def generate(self, input: AchievementDistillationInput) -> AchievementDistillationOutput`.
- `PolishCvAdapter` maps the internal input to the existing `polish_cv` behavior and distinguishes `polished`, `fallback`, and `parse_failed`.
- `FakeAdapter` accepts `dict[str, AchievementDistillationOutput]` for offline tests.
- `run_cases(cases: list[EvaluationCase], adapter: DistillationAdapter) -> list[EvaluationResult]`.
- `summarize(results: list[EvaluationResult]) -> HarnessReport`.
- CLI options: `--dataset`, `--output`, `--category`, `--fake-fixture`; default dataset is the v1 JSON file and default output is stdout JSON.

- [ ] **Step 1: Write failing runner and report tests**

```python
@pytest.mark.asyncio
async def test_runner_preserves_case_id_and_generator_status():
    adapter = FakeAdapter({
        "golden_001": AchievementDistillationOutput(
            cv="优化支付流程，成功率提升 15%",
            follow_up_questions=[],
            generator_status="polished",
        )
    })
    results = await run_cases([case("golden_001")], adapter)
    assert results[0].case_id == "golden_001"
    assert results[0].output.generator_status == "polished"


def test_report_contains_category_rates_and_failures():
    report = summarize([passing_result("golden_001"), failing_result("boundary_001")])
    assert report.total == 2
    assert report.by_category["golden"].passed == 1
    assert report.failures[0].case_id == "boundary_001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_runner.py app/tests/harness/test_report.py -v`

Expected: FAIL because the adapter, runner, report types, and CLI do not exist.

- [ ] **Step 3: Implement adapter, runner, report, and CLI**

The runner must execute cases in dataset order, call the adapter exactly once per case, run L1 on every output including fallback and parse failure, calculate `passed` from P0 hard checks plus the case’s expected behavior, preserve failure details, and emit stable JSON suitable for CI artifacts.

The report must include total counts, category pass rates, P0 violation counts, generator status counts, and an ordered list of failures. It must not call an LLM.

- [ ] **Step 4: Run the fake-fixture harness**

Run: `python app/scripts/run_achievement_harness.py --fake-fixture --output /tmp/achievement-harness-report.json`

Expected: command exits successfully and the report contains 30 case results, category rates, and failures if the fixture intentionally includes them.

- [ ] **Step 5: Run tests and commit**

Run: `pytest app/tests/harness/test_runner.py app/tests/harness/test_report.py -v`

```bash
git add app/harness app/scripts/run_achievement_harness.py app/tests/harness/test_runner.py app/tests/harness/test_report.py
git commit -m "feat: add achievement harness runner"
```

## Task 4: Add CI regression gate and version metadata

**Files:**
- Create: `app/harness/gate.py`
- Create: `app/tests/harness/test_regression_gate.py`
- Modify: `app/scripts/run_achievement_harness.py`
- Modify: the repository’s existing `.github/workflows/*` file after locating its current test workflow
- Modify: `docs/harness/achievement-distillation-harness-v1.md` with an implementation-status appendix

**Interfaces:**
- `evaluate_gate(report: HarnessReport) -> GateDecision`.
- `GateDecision` fields: `passed: bool`, `blocking_reasons: list[str]`, `metrics: dict[str, float]`.
- Every report includes `model_version`, `prompt_version`, `dataset_version`, and `harness_version`.

- [ ] **Step 1: Write failing gate tests**

```python
def test_gate_blocks_unsupported_number_even_with_high_average_score():
    report = report_with_metrics(
        adversarial_pass_rate=1.0,
        unsupported_number_rate=0.01,
        golden_pass_rate=1.0,
        boundary_pass_rate=1.0,
    )
    decision = evaluate_gate(report)
    assert decision.passed is False
    assert "unsupported_number_rate" in decision.blocking_reasons


def test_gate_accepts_v1_thresholds():
    report = report_with_metrics(
        adversarial_pass_rate=1.0,
        unsupported_number_rate=0.0,
        unsupported_entity_rate=0.0,
        schema_pass_rate=1.0,
        golden_pass_rate=0.8,
        boundary_pass_rate=0.9,
        semantic_average=3.5,
    )
    assert evaluate_gate(report).passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_regression_gate.py -v`

Expected: FAIL because the gate and versioned report metadata do not exist.

- [ ] **Step 3: Implement the gate**

Apply these exact thresholds:

```text
adversarial_pass_rate       == 1.0
unsupported_number_rate     == 0.0
unsupported_entity_rate     == 0.0
schema_pass_rate            == 1.0
boundary_pass_rate          >= 0.90
golden_pass_rate            >= 0.80
semantic_average            >= 3.5
```

The CLI must return exit code 1 when the gate fails and exit code 0 when it passes. Include metadata in the report rather than reading versions from an ambient environment variable.

- [ ] **Step 4: Run the gate against the full fake dataset**

Run: `python app/scripts/run_achievement_harness.py --fake-fixture --gate`

Expected: exit code reflects the fixture report and stdout includes every blocking reason.

- [ ] **Step 5: Wire the command into existing CI and commit**

Use the existing workflow conventions. Do not add a new CI provider. The CI step must run without an API key by using the deterministic fake fixture for the structural gate; live LLM evaluation remains an explicitly separate command.

```bash
git add app/harness/gate.py app/tests/harness/test_regression_gate.py app/scripts/run_achievement_harness.py .github/workflows docs/harness
git commit -m "ci: gate achievement distillation regressions"
```

## Task 5: Add runtime trace and guardrail recording

**Files:**
- Create: `app/harness/trace.py`
- Create: `app/tests/harness/test_trace.py`
- Modify: `app/api/llm.py` at the `polish_cv` boundary only
- Modify: existing SQLite storage/model files after locating the project’s migration/schema pattern
- Create: `app/tests/test_api_polish_cv_harness.py`

**Interfaces:**
- `create_distillation_trace(input, output, metadata, guardrail_results) -> str`.
- `record_distillation_trace(trace: DistillationTrace) -> None`.
- `TraceMetadata` fields: `model_version`, `prompt_version`, `dataset_version`, `harness_version`, `latency_ms`.
- Trace fields include `input_hash`, `raw_output`, `parsed_output`, `generator_status`, `guardrail_results`, `final_quality_status`, and error summary.

- [ ] **Step 1: Write failing trace and API regression tests**

```python
def test_fallback_trace_is_not_polished(client):
    response = client.post(
        "/api/llm/polish_cv",
        json={"task_title": "X", "outcome": "完成"},
    )
    assert response.status_code == 200
    trace = read_latest_trace()
    assert trace.generator_status == "fallback"
    assert trace.final_quality_status in {"pending", "needs_data"}


def test_trace_does_not_write_raw_outcome_to_application_log(caplog, client):
    client.post("/api/llm/polish_cv", json={"task_title": "X", "outcome": "敏感原文"})
    assert "敏感原文" not in caplog.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_trace.py app/tests/test_api_polish_cv_harness.py -v`

Expected: FAIL because no trace persistence or API integration exists.

- [ ] **Step 3: Implement trace persistence and boundary integration**

Record trace data on success, fallback, parse failure, and exception. Use a stable SHA-256 input hash. Store full raw/parsed payloads in the local audit store; application logs contain only trace id, status, latency, and error summary.

Trace recording failure must not turn a successful `polish_cv` response into HTTP 500; log the persistence error without exposing raw outcome text.

- [ ] **Step 4: Run API and backend regression tests**

Run: `rm -rf app/llm/__pycache__ && pytest app/tests/test_api_polish_cv.py app/tests/test_api_polish_cv_harness.py app/tests/test_api_complete_task.py -v`

Expected: all existing polish/complete tests and new trace tests PASS.

- [ ] **Step 5: Commit runtime observability**

```bash
git add app/harness/trace.py app/tests/harness/test_trace.py app/tests/test_api_polish_cv_harness.py app/api/llm.py app/core
git commit -m "feat: trace achievement distillation calls"
```

## Task 6: Add feedback diff classification and documentation handoff

**Files:**
- Create: `app/harness/feedback.py`
- Create: `app/tests/harness/test_feedback.py`
- Modify: the achievement update path used by `update_achievement` after verifying its current API contract
- Modify: `docs/harness/achievement-distillation-harness-v1.md` with an implementation-status appendix
- Create: `docs/changelog/2026-08-08-achievement-distillation-harness.md`

**Interfaces:**
- `classify_cv_edit(original: str, final: str) -> Literal["accepted", "minor_edit", "major_edit", "rewritten", "rejected"]`.
- `record_feedback(trace_id: str, original_cv: str, final_cv: str, edit_type: str, diff: str) -> None`.

- [ ] **Step 1: Write failing classification tests**

```python
def test_identical_cv_is_accepted():
    assert classify_cv_edit("优化登录流程", "优化登录流程") == "accepted"


def test_small_edit_is_minor():
    assert classify_cv_edit("优化登录流程", "优化登录流程，降低耗时") == "minor_edit"


def test_large_rewrite_is_rewritten():
    assert classify_cv_edit("优化登录流程", "建立支付风控体系并覆盖多个场景") == "rewritten"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest app/tests/harness/test_feedback.py -v`

Expected: FAIL because the classifier and feedback persistence do not exist.

- [ ] **Step 3: Implement deterministic diff classification**

Use normalized character-level similarity and length delta. Keep thresholds explicit in code and test them at boundary values. Do not infer why the user edited the text; store only the edit class and diff for later human review.

- [ ] **Step 4: Wire feedback to the existing achievement update path**

When a CV changes, look up the associated trace id if present, classify the edit, and record feedback. If no trace exists for a legacy achievement, skip feedback without changing the update response.

- [ ] **Step 5: Run full verification and write the changelog**

Run:

```bash
pytest app/tests/harness app/tests/test_api_polish_cv.py app/tests/test_api_complete_task.py app/tests/test_api_answer_follow_ups.py -v
cd web && npx tsc --noEmit
```

Write the changelog entry with the actual test counts and the final supported subset of the Harness contract.

- [ ] **Step 6: Commit the feedback loop**

```bash
git add app/harness app/tests/harness docs/harness docs/changelog
git commit -m "feat: close achievement distillation feedback loop"
```

## Verification Checklist

Before claiming the Harness is complete:

- [ ] `pytest app/tests/harness -v` passes.
- [ ] Existing `polish_cv`, complete-task, and follow-up tests pass.
- [ ] Full fake dataset produces a stable JSON report.
- [ ] Gate blocks unsupported numbers/entities and adversarial failures.
- [ ] Fallback and parse failure are distinguishable from polished generation.
- [ ] Trace metadata contains model, prompt, dataset, harness versions and latency.
- [ ] Raw outcome text is absent from ordinary application logs.
- [ ] User CV edits produce feedback classifications when a trace id exists.
- [ ] `cd web && npx tsc --noEmit` passes.
- [ ] No `next build` was run while the dev server is active.

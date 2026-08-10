# Project Harness v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local project-level release gate that validates committed Cockpit capabilities, constitutional boundaries, dependencies, and existing capability harnesses without treating future roadmap gaps as regressions.

**Architecture:** A versioned YAML capability registry describes which capabilities are implemented, blocking, and release-scoped. `app.harness.project_gate` validates the registry, preflights declared dependencies, invokes an allowlisted verification command for each release-scoped implemented capability, and emits one stable JSON decision. Deterministic L2 constitutional tests and the report-readiness invariant join the same gate; real-model semantic evaluation remains an explicit separate command.

**Tech Stack:** Python 3.12, PyYAML, pytest, FastAPI/SQLAlchemy, Next.js/TypeScript, Node 22, Make.

## Global Constraints

- Preserve local-first operation; do not add cloud telemetry, remote CI, automatic code changes, or automatic deployment.
- `ready` is the sole formal-output eligibility state. `needs_data` and `pending` remain recoverable assets but never appear in report/CV output.
- No endpoint or UI may set `cv_status=ready` directly; readiness is derived at the storage boundary from completion evidence or complete follow-up answers.
- A registry item with `status: future` is reported as a capability gap and must never make the current project gate fail.
- A release-scoped implemented capability with a missing declared dependency is a blocking failure with an actionable install command.
- Do not run `next build`; verify frontend changes with `npx tsc --noEmit` and existing Node core scripts.
- Preserve the user’s unrelated untracked `docs/superpowers/plans/2026-08-10-goal-constitution-alignment.md`.

---

### Task 1: Define and validate the capability registry

**Files:**
- Create: `docs/harness/capabilities-v1.yaml`
- Create: `app/harness/capabilities.py`
- Modify: `pyproject.toml:40-47`
- Create: `app/tests/harness/test_capabilities.py`

**Interfaces:**
- Consumes: `docs/harness/capabilities-v1.yaml`.
- Produces: `CapabilitySpec(id: str, status: Literal["implemented", "future"], risk_level: Literal["read", "write", "destructive"], release_suite: bool, command: list[str], required_dependencies: list[str])` and `load_capabilities(path: Path | None = None) -> list[CapabilitySpec]`.

- [ ] **Step 1: Write failing registry tests**

```python
def test_default_registry_has_unique_capability_ids() -> None:
    capabilities = load_capabilities()
    assert {item.id for item in capabilities} == {
        "achievement_distillation", "report_composition", "mcp_write_path",
        "constitution", "refiner", "git_candidate", "composer",
    }
    assert len({item.id for item in capabilities}) == len(capabilities)


def test_future_capability_cannot_be_release_scoped(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text("capabilities:\\n  - id: refiner\\n    status: future\\n    risk_level: read\\n    release_suite: true\\n    command: []\\n    required_dependencies: []\\n")
    with pytest.raises(ValueError, match="future capability.*release_suite"):
        load_capabilities(path)
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run: `.venv312/bin/pytest app/tests/harness/test_capabilities.py -v`  
Expected: FAIL because `app.harness.capabilities` does not exist.

- [ ] **Step 3: Add the development-only YAML dependency and registry fixture**

Add `PyYAML>=6.0` to `[project.optional-dependencies].dev`. Create the registry with these exact items:

```yaml
capabilities:
  - id: achievement_distillation
    status: implemented
    risk_level: write
    release_suite: true
    command: [".venv312/bin/pytest", "app/tests/harness", "app/tests/test_api_polish_cv_harness.py", "-q"]
    required_dependencies: []
  - id: report_composition
    status: implemented
    risk_level: write
    release_suite: true
    command: [".venv312/bin/pytest", "app/tests/test_report_workspace_invariants.py", "app/tests/test_complete_modal_minimal_invariants.py", "-q"]
    required_dependencies: []
  - id: mcp_write_path
    status: implemented
    risk_level: write
    release_suite: true
    command: [".venv312/bin/pytest", "app/tests/test_mcp_server.py", "-q"]
    required_dependencies: ["mcp"]
  - id: constitution
    status: implemented
    risk_level: destructive
    release_suite: true
    command: [".venv312/bin/pytest", "app/tests/constitution", "-q"]
    required_dependencies: []
  - id: refiner
    status: future
    risk_level: read
    release_suite: false
    command: []
    required_dependencies: []
  - id: git_candidate
    status: future
    risk_level: write
    release_suite: false
    command: []
    required_dependencies: []
  - id: composer
    status: future
    risk_level: read
    release_suite: false
    command: []
    required_dependencies: []
```

Install development dependencies into the active project environment with `.venv312/bin/python -m pip install -e '.[dev]'` before exercising the MCP entry.

- [ ] **Step 4: Implement strict loader validation**

Implement Pydantic-backed validation in `app/harness/capabilities.py`. Reject unknown fields, duplicate ids, an implemented item without a command, and any future item that is release-scoped. Resolve the default registry relative to the repository root, not the current directory.

- [ ] **Step 5: Run registry tests to verify they pass**

Run: `.venv312/bin/pytest app/tests/harness/test_capabilities.py -v`  
Expected: PASS.

- [ ] **Step 6: Commit the registry contract**

```bash
git add pyproject.toml docs/harness/capabilities-v1.yaml app/harness/capabilities.py app/tests/harness/test_capabilities.py
git commit -m "feat(harness): register project capabilities"
```

### Task 2: Build the project-gate runner and stable JSON contract

**Files:**
- Create: `app/harness/project_gate.py`
- Create: `app/scripts/run_project_gate.py`
- Create: `app/tests/harness/test_project_gate.py`
- Modify: `Makefile:1-8,48-50`

**Interfaces:**
- Consumes: `list[CapabilitySpec]` from Task 1.
- Produces: `CheckResult(id: str, status: Literal["passed", "blocking_failure", "capability_gap"], reason: str | None, command: list[str])`, `ProjectGateReport(passed: bool, checks: list[CheckResult], capability_gaps: list[str], blocking_reasons: list[str])`, and `run_project_gate(capabilities: list[CapabilitySpec], runner: CommandRunner) -> ProjectGateReport`.

- [ ] **Step 1: Write failing gate unit tests**

```python
def test_future_capability_is_reported_without_blocking() -> None:
    report = run_project_gate([future("refiner")], runner=FakeRunner())
    assert report.passed is True
    assert report.capability_gaps == ["refiner"]
    assert report.checks[0].status == "capability_gap"


def test_missing_dependency_is_actionable_blocking_failure() -> None:
    report = run_project_gate([implemented("mcp_write_path", dependencies=["mcp"])], runner=FakeRunner())
    assert report.passed is False
    assert report.blocking_reasons == ["mcp_write_path:missing_dependency:mcp"]
    assert report.checks[0].reason == "missing_dependency:mcp; install: pip install -e '.[dev]'"


def test_failed_capability_command_is_a_blocking_failure() -> None:
    report = run_project_gate([implemented("constitution")], runner=FakeRunner(exit_code=1))
    assert report.checks[0].status == "blocking_failure"
    assert report.blocking_reasons == ["constitution:command_failed"]
```

- [ ] **Step 2: Run gate tests to verify they fail**

Run: `.venv312/bin/pytest app/tests/harness/test_project_gate.py -v`  
Expected: FAIL because `project_gate` does not exist.

- [ ] **Step 3: Implement the runner without shell interpolation**

Use `importlib.util.find_spec(dependency)` for preflight. Invoke each registry `command` via `subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)`; never pass a string command or `shell=True`. Return command stdout/stderr only in a bounded diagnostic field for a failed check. Sort checks by registry order so JSON is stable.

The CLI must support `--registry PATH` and `--output PATH`, print JSON to stdout when no output is requested, and return `0` only when `report.passed` is true.

- [ ] **Step 4: Add the Make entry point**

Add `project-gate` to `.PHONY`, help output, and the target:

```make
project-gate:
	@.venv312/bin/python app/scripts/run_project_gate.py
```

- [ ] **Step 5: Run deterministic gate tests to verify they pass**

Run: `.venv312/bin/pytest app/tests/harness/test_project_gate.py -v`  
Expected: PASS.

- [ ] **Step 6: Verify the real preflight diagnosis before dependencies are installed**

Run: `make project-gate`  
Expected: nonzero exit; JSON contains `mcp_write_path:missing_dependency:mcp`, not a subprocess traceback.

- [ ] **Step 7: Commit the project gate**

```bash
git add app/harness/project_gate.py app/scripts/run_project_gate.py app/tests/harness/test_project_gate.py Makefile
git commit -m "feat(harness): add local project gate"
```

### Task 3: Close the report-readiness bypass at its data and UI boundaries

**Files:**
- Modify: `web/lib/templates.ts`
- Modify: `web/app/report/page.tsx`
- Modify: `app/core/models.py:278-283`
- Modify: `app/core/storage.py:846-866`
- Modify: `app/api/achievements.py:42-47`
- Modify: `web/lib/api.ts:424`
- Modify: `app/tests/test_report_workspace_invariants.py`
- Modify: `app/tests/test_api_achievements_cv_status.py`
- Create: `web/scripts/test-report-readiness.mjs`

**Interfaces:**
- Consumes: `Achievement.cv_status` and existing `storage.complete_task` / `storage.answer_follow_ups` readiness derivation.
- Produces: `generateReport()` whose input is filtered to `ready`, `AchievementUpdate(cv: str | None)` with no public status override, and an edit operation that retains its existing non-ready status unless the established follow-up-completion path promotes it.

- [ ] **Step 1: Write the failing output-safety tests**

Add a Node test using three same-project achievements:

```ts
const report = generateReport([
  achievement("ready", "上线核心功能并完成验收"),
  achievement("needs_data", "优化内容，缺少指标"),
  achievement("pending", "草稿"),
], range, TEMPLATES[0]);
assert.equal(report.usedAchievements.length, 1);
assert(report.markdown.includes("上线核心功能并完成验收"));
assert(!report.markdown.includes("优化内容，缺少指标"));
assert(!report.markdown.includes("草稿"));
```

Add API tests asserting `PATCH /api/achievements/{id}` rejects a body containing `cv_status`, and source-invariant tests asserting `report/page.tsx` contains no `updateAchievement(a.id, { cv_status: "ready" })` call.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `node --experimental-strip-types web/scripts/test-report-readiness.mjs`  
Expected: FAIL because weekly templates include `needs_data`.

Run: `.venv312/bin/pytest app/tests/test_api_achievements_cv_status.py app/tests/test_report_workspace_invariants.py -v`  
Expected: FAIL because the endpoint and report UI accept direct status promotion.

- [ ] **Step 3: Implement the narrow readiness policy**

Make every `TemplateSection.match` require `a.cv_status === "ready"`; remove the `[📊 差数据]` output marker because those assets no longer enter output. Keep the report page’s non-ready cards only as links to `/achievements/follow-up` or `/achievements`, not as status-writing controls.

Remove `cv_status` from `AchievementUpdate` and from `api.updateAchievement`’s TypeScript request type. Keep `update_achievement_cv` focused on updating the CV text and feedback trace; it must not write `cv_status`. Existing `complete_task` and `answer_follow_ups` remain the only paths that derive/promote readiness.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `node --experimental-strip-types web/scripts/test-report-readiness.mjs`  
Expected: PASS.

Run: `.venv312/bin/pytest app/tests/test_api_achievements_cv_status.py app/tests/test_report_workspace_invariants.py -v`  
Expected: PASS with updated API contract tests.

- [ ] **Step 5: Commit the readiness boundary**

```bash
git add web/lib/templates.ts web/app/report/page.tsx web/lib/api.ts web/scripts/test-report-readiness.mjs app/core/models.py app/core/storage.py app/api/achievements.py app/tests/test_report_workspace_invariants.py app/tests/test_api_achievements_cv_status.py
git commit -m "fix(reports): enforce ready-only output eligibility"
```

### Task 4: Add deterministic L2 constitutional regression tests

**Files:**
- Create: `app/tests/constitution/__init__.py`
- Create: `app/tests/constitution/test_output_and_write_boundaries.py`
- Create: `app/tests/constitution/test_irreversible_actions.py`
- Modify: `app/tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `storage.complete_task`, `storage.answer_follow_ups`, `POST /api/llm/polish_cv`, report template functions, and the deletion confirmation path in `app/llm/chat_engine.py`.
- Produces: executable L2 tests for C-002/C-003/C-004 and the MCP shared-write invariant.

- [ ] **Step 1: Write the initial failing constitutional tests**

```python
@pytest.mark.asyncio
async def test_incomplete_completion_never_becomes_ready(temp_db) -> None:
    task = await seeded_task("发布登录优化")
    achievement = await storage.complete_task(
        task.id, outcome="已完成", cv="完成「发布登录优化」", cv_status=CVStatus.READY,
    )
    assert achievement.cv_status is CVStatus.NEEDS_DATA


def test_project_deletion_requires_explicit_confirmation_protocol() -> None:
    prompt = Path("app/llm/prompts/cockpit_system.md").read_text(encoding="utf-8")
    assert "delete_project" in prompt
    assert "明确确认" in prompt
```

Add tests that reuse the public polish endpoint’s unsupported-number response and assert that `generateReport` cannot accept non-ready assets. Add an MCP end-to-end assertion that a short/fallback completion produces `needs_data`, not caller-requested `ready`.

- [ ] **Step 2: Run the new constitutional tests to verify their pre-fix state**

Run: `.venv312/bin/pytest app/tests/constitution -v`  
Expected: some tests are red until Task 3 has removed the output/status bypass; retain any already-green shared-write tests as regression coverage.

- [ ] **Step 3: Make only boundary-oriented test and code adjustments**

Do not implement a simulated “team feature refusal” prompt test. Keep this suite deterministic: storage state, runtime P0 guardrail, report eligibility, MCP shared completion path, and the existing destructive confirmation protocol must be directly observable.

- [ ] **Step 4: Run constitutional and MCP tests**

Run: `.venv312/bin/pytest app/tests/constitution app/tests/test_mcp_server.py -v`  
Expected: PASS after Task 1’s dev dependency installation.

- [ ] **Step 5: Commit the L2 suite**

```bash
git add app/tests/constitution app/tests/test_mcp_server.py
git commit -m "test(constitution): cover deterministic safety boundaries"
```

### Task 5: Validate the integrated gate and record the operating contract

**Files:**
- Modify: `README.md:15-24`
- Create: `docs/changelog/2026-08-10-project-harness-v1.md`
- Modify: `docs/changelog/README.md`

**Interfaces:**
- Consumes: `make project-gate`, capability registry, all release-scoped verification commands.
- Produces: operator documentation explaining offline project gate vs optional live semantic evaluation and an auditable changelog decision.

- [ ] **Step 1: Write failing command-contract tests**

Add to `app/tests/harness/test_project_gate.py`:

```python
def test_default_registry_gate_passes_when_all_declared_commands_pass() -> None:
    report = run_project_gate(load_capabilities(), runner=AllPassingRunner(available_modules={"mcp"}))
    assert report.passed is True
    assert report.capability_gaps == ["refiner", "git_candidate", "composer"]
```

- [ ] **Step 2: Run the command-contract test**

Run: `.venv312/bin/pytest app/tests/harness/test_project_gate.py -v`  
Expected: PASS after Tasks 1–2; this proves future entries cannot poison a healthy release decision.

- [ ] **Step 3: Document the operator flow**

Document exactly two commands:

```bash
make project-gate
.venv312/bin/python app/scripts/run_achievement_harness.py --suite current_baseline --semantic-judge --gate
```

The first is the required offline release gate. The second is mandatory before changing LLM provider/model/prompt when a verified LLM client is configured; absence of a semantic judge is an explicit no-release result for that AI change, not a fake score.

- [ ] **Step 4: Run full verification**

Run: `make project-gate`  
Expected: exit 0 and JSON `passed: true`, with exactly three future capability gaps.

Run: `.venv312/bin/pytest app/tests/ -v`  
Expected: all backend tests pass, including MCP tests.

Run: `node --experimental-strip-types web/scripts/test-report-readiness.mjs`  
Expected: PASS.

Run: `node --experimental-strip-types web/scripts/test-achievement-stats.mjs`  
Expected: PASS.

Run: `node --experimental-strip-types web/scripts/test-cv-template.mjs`  
Expected: PASS.

Run: `cd web && npx tsc --noEmit`  
Expected: exit 0.

- [ ] **Step 5: Confirm the scope is clean and commit**

Run: `git diff --check`  
Expected: no whitespace errors; the only untracked file remains the user-owned goal-alignment plan.

```bash
git add README.md docs/changelog/2026-08-10-project-harness-v1.md docs/changelog/README.md app/tests/harness/test_project_gate.py
git commit -m "docs: document project harness v1"
```

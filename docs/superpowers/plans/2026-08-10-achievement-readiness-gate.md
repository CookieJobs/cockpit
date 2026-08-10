# Achievement Readiness Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every completion while preventing incomplete achievements from being marked `ready` and used in generated outputs.

**Architecture:** Enforce the status invariant once in `app.core.storage.complete_task`, the shared write boundary used by web, chat tools, and MCP. Follow-up completion derives readiness from whether every stored question has a non-empty answer. The modal only changes its copy to make the resulting state understandable; it does not reproduce the business rule.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/SQLite, pytest, Next.js/TypeScript.

## Global Constraints

- Keep Cockpit local-first and introduce no external service.
- Do not block task completion or create destructive behavior.
- Do not weaken fact-grounding guardrails in the existing uncommitted Harness work.
- Treat `ready` as the only status eligible for report/PR/CV output.
- Preserve explicit `pending` when the user requested it.

---

### Task 1: Lock readiness derivation with storage tests

**Files:**
- Modify: `app/tests/test_storage.py`
- Modify: `app/tests/test_api_complete_task.py`

**Interfaces:**
- Consumes: `storage.complete_task(task_id, outcome, cv, cv_status, follow_up_questions)`.
- Produces: tests that require incomplete completion evidence to persist as `CVStatus.NEEDS_DATA`.

- [x] **Step 1: Write failing storage tests**

```python
achievement = await storage.complete_task(
    task.id,
    outcome="完成登录优化",
    cv="完成「登录优化」",
    cv_status=CVStatus.READY,
)
assert achievement.cv_status == CVStatus.NEEDS_DATA
```

Add equivalent cases for an outcome shorter than ten trimmed characters and for a non-empty `follow_up_questions` list.

- [x] **Step 2: Run the focused tests to verify they fail**

Run: `pytest app/tests/test_storage.py app/tests/test_api_complete_task.py -v`

Expected: the new tests fail because the current storage function persists the caller's `ready` value.

- [x] **Step 3: Write failing follow-up lifecycle tests**

```python
partial = await storage.answer_follow_ups(achievement.id, {"0": "已覆盖一半"})
assert partial.cv_status == CVStatus.NEEDS_DATA
complete = await storage.answer_follow_ups(achievement.id, {"1": "其余范围"})
assert complete.cv_status == CVStatus.READY
```

- [x] **Step 4: Run the focused tests to verify they fail**

Run: `pytest app/tests/test_storage.py -v`

Expected: partial-answer test fails because the current code promotes after any non-empty answer.

### Task 2: Implement the shared readiness gate

**Files:**
- Modify: `app/core/storage.py`

**Interfaces:**
- Consumes: completion values passed to `complete_task`.
- Produces: `_derive_completion_cv_status(task_title, outcome, cv, requested_status, follow_up_questions) -> CVStatus` and complete-answer promotion in `answer_follow_ups`.

- [x] **Step 1: Add the minimal status helper**

```python
def _derive_completion_cv_status(...):
    if has_unanswered_questions or is_title_fallback or len(outcome.strip()) < 10:
        return CVStatus.NEEDS_DATA
    return requested_status
```

- [x] **Step 2: Apply it before creating `AchievementORM`**

Pass the derived status rather than the caller-provided status to `AchievementORM.cv_status`.

- [x] **Step 3: Promote only when all persisted questions have non-empty answers**

```python
questions = json.loads(a.follow_up_questions_json or "[]")
if questions and all((existing.get(str(i)) or "").strip() for i in range(len(questions))):
    a.cv_status = CVStatus.READY.value
```

For a legacy achievement without questions, retain its current status.

- [x] **Step 4: Run focused tests to verify green**

Run: `pytest app/tests/test_storage.py app/tests/test_api_complete_task.py -v`

Expected: all tests pass.

### Task 3: Make deferred readiness legible in the completion modal

**Files:**
- Modify: `web/components/CompleteTaskModal.tsx`
- Modify: `app/tests/test_complete_modal_minimal_invariants.py`

**Interfaces:**
- Consumes: modal state `cv`, `outcome`, and `followUpQuestions`.
- Produces: explanatory copy that the program will save incomplete work as `needs_data` and exclude it from reports until supplemented.

- [x] **Step 1: Add a failing source invariant test**

Assert that the modal contains the deferred-readiness message and does not claim an incomplete item is immediately report-ready.

- [x] **Step 2: Run it to verify red**

Run: `pytest app/tests/test_complete_modal_minimal_invariants.py -v`

Expected: the new assertion fails because the message does not exist.

- [x] **Step 3: Add minimal conditional copy**

Show a small, non-blocking message when follow-ups exist or the CV equals `完成「${task.title}」`: “将保存为待补数据，不会进入报告；补全后自动可用”。

- [x] **Step 4: Run the modal invariant test to verify green**

Run: `pytest app/tests/test_complete_modal_minimal_invariants.py -v`

Expected: all tests pass.

### Task 4: Document and verify the end-to-end contract

**Files:**
- Create: `docs/changelog/2026-08-10-achievement-readiness-gate.md`
- Modify: `docs/lessons/01-frontend-ux-bugs.md`

- [x] **Step 1: Record the decision and its user-visible consequence**

Document why completion and output-readiness differ, the deterministic triggers, and the recovery path.

- [x] **Step 2: Record the regression lesson**

Add a lesson that a status value controlled by the UI cannot be the authority for output eligibility when its required evidence is computed elsewhere.

- [x] **Step 3: Run full verification**

Run: `.venv312/bin/pytest app/tests/ --ignore=app/tests/test_mcp_server.py -v && (cd web && npx tsc --noEmit)`

Result: 392 passed, 2 skipped; TypeScript reports no errors. The unignored MCP suite cannot initialize because the existing `.venv312` lacks the declared `mcp` package; this scope does not alter dependencies.

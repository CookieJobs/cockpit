# Project-Local Completed Task Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep completed tasks visibly credited inside their expanded project card, below active tasks, while preserving active-first project management.

**Architecture:** `build_snapshot` already reads every task once and partitions active from completed work. Extend its per-project projection with a completed-task list, while leaving `ProjectSnapshot.tasks` as active-only and the top-level `Snapshot.done_tasks` intact for compatibility. The project card consumes the two lists as separate regions: DnD and task creation use only active tasks; a small dedicated completed-row component renders permanent history and reuses the existing task-id undo route.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / Pydantic v2 / pytest; Next.js 15 / React / TypeScript / Tailwind / dnd-kit.

## Global Constraints

- `ProjectSnapshot.tasks` remains the active-task list; do not change its meaning or make another tasks request.
- Add `ProjectSnapshot.done_tasks: list[Task]`; it contains only this project's completed tasks, newest completion date first, with deterministic tie-breaking.
- Keep top-level `Snapshot.done_tasks` and its existing ordering unchanged for compatibility, but remove the dead `LegacyCompletedTaskView` implementation rather than adding a second completed-task UI.
- Project UI order is fixed: active task list, add-task control, then an always-visible completed region when non-empty. The completed region has no collapse control.
- Header progress means `completed / (active + completed)`, independent of achievement readiness or checklist progress.
- Completed rows are not draggable, not inline-editable, not focus candidates, and have no second completion action. They only expose explicit confirmed undo.
- Preserve existing completion, undo persistence, achievement creation/readiness, API endpoints, theme tokens, and `include_completed=False` list default.
- Do not touch or stage user-owned changes in `web/components/ProjectEmojiPicker.tsx`, `web/app/globals.css`, `.workbuddy/`, or unrelated untracked documents.
- Use `./.venv/bin/python -m pytest`; do not run `next build` because it pollutes an active dev server's `.next/` directory.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `app/core/models.py` | Add the per-project completed-task snapshot contract. |
| `app/core/storage.py` | Derive and order completed tasks once, then attach them to each project snapshot. |
| `app/tests/test_storage.py` | Assert mixed-project snapshot membership, completion order, and active-list compatibility. |
| `web/lib/api.ts` | Mirror the new API field in the TypeScript `ProjectSnapshot` interface. |
| `web/components/MainBoard.tsx` | Render active work, add-task control, and permanent completed history in that order; retire the legacy global view. |
| `app/tests/test_project_completed_task_visibility.py` | Source-level UI/contract guardrails for progress, DnD boundary, permanent region, undo, and legacy-view removal. |

---

### Task 1: Extend the project snapshot with completed-task history

**Files:**
- Modify: `app/core/models.py:353-364`
- Modify: `app/core/storage.py:1604-1696`
- Modify: `app/tests/test_storage.py:396-496`

**Interfaces:**
- Consumes: existing `Task.status`, `Task.completed_at`, `Task.sort_order`, `Task.id`, `TaskStatus.COMPLETED`, and `storage.complete_task`.
- Produces: `ProjectSnapshot.done_tasks: list[Task]`, where `tasks` remains active-only and `done_count == len(done_tasks)`.

- [ ] **Step 1: Write the failing mixed-project snapshot test**

  Add `from datetime import date` beside the existing imports in `app/tests/test_storage.py`, then add the following test immediately after `test_build_snapshot_groups_by_project`:

  ```python
  @pytest.mark.asyncio
  async def test_build_snapshot_keeps_project_completed_tasks_separate_and_ordered(
      temp_db, monkeypatch
  ):
      """Project snapshot exposes its completed history without polluting active work."""
      p1 = await storage.add_project(ProjectCreate(name="P1"))
      p2 = await storage.add_project(ProjectCreate(name="P2"))
      active = await storage.add_task(TaskCreate(project=p1.id, title="仍在进行"))
      older = await storage.add_task(TaskCreate(project=p1.id, title="较早完成"))
      newer = await storage.add_task(TaskCreate(project=p1.id, title="较晚完成"))
      other_project_done = await storage.add_task(TaskCreate(project=p2.id, title="P2 完成"))

      class FrozenDate(date):
          current = date(2026, 8, 1)

          @classmethod
          def today(cls):
              return cls.current

      monkeypatch.setattr(storage, "date", FrozenDate)
      await storage.complete_task(older.id, outcome="o", cv="cv", cv_status=CVStatus.PENDING)
      FrozenDate.current = date(2026, 8, 2)
      await storage.complete_task(newer.id, outcome="o", cv="cv", cv_status=CVStatus.PENDING)
      await storage.complete_task(
          other_project_done.id, outcome="o", cv="cv", cv_status=CVStatus.PENDING
      )

      snapshot = await storage.build_snapshot()
      by_id = {project.id: project for project in snapshot.projects}

      assert [task.id for task in by_id[p1.id].tasks] == [active.id]
      assert [task.id for task in by_id[p1.id].done_tasks] == [newer.id, older.id]
      assert by_id[p1.id].done_count == 2
      assert [task.id for task in by_id[p2.id].done_tasks] == [other_project_done.id]
      assert all(task.status != TaskStatus.COMPLETED for task in by_id[p1.id].tasks)
      assert {task.id for task in snapshot.done_tasks} == {
          older.id, newer.id, other_project_done.id
      }
  ```

- [ ] **Step 2: Run the new test and verify it fails for the missing contract**

  Run:

  ```bash
  ./.venv/bin/python -m pytest app/tests/test_storage.py::test_build_snapshot_keeps_project_completed_tasks_separate_and_ordered -v
  ```

  Expected: FAIL with an `AttributeError` or Pydantic validation error because `ProjectSnapshot` has no `done_tasks` field.

- [ ] **Step 3: Add the backend snapshot contract and one-pass grouping**

  In `app/core/models.py`, extend `ProjectSnapshot` without changing `tasks`:

  ```python
  class ProjectSnapshot(CockpitModel):
      """项目快照（活动任务 + 已完成任务）。"""
      id: Optional[str]
      name: str
      description: str = ""
      tasks: list[Task]
      done_tasks: list[Task] = []
      done_count: int = 0
      emoji: Optional[str] = None
  ```

  In `app/core/storage.py`, keep the existing global `active_tasks` / `done_tasks` split and top-level `Snapshot.done_tasks` return intact. Add a local ordering helper after that split:

  ```python
  def completed_task_sort_key(task: Task) -> tuple[int, int, str]:
      completed = task.completed_at or date.min
      return (-completed.toordinal(), task.sort_order, task.id)
  ```

  In the project loop, replace the count-only projection with the ordered list and pass it to the snapshot:

  ```python
  p_active = [task for task in active_tasks if task.project == p.id]
  p_done = sorted(
      (task for task in done_tasks if task.project == p.id),
      key=completed_task_sort_key,
  )
  projects_grouped.append(ProjectSnapshot(
      id=p.id,
      name=p.name,
      description=p.description,
      tasks=p_active,
      done_tasks=p_done,
      done_count=len(p_done),
      sort_order=p.sort_order,
      emoji=p.emoji,
  ))
  ```

  Give the ungrouped active-task pseudo-project `done_tasks=[]` explicitly. Do not add completed orphan tasks to it: project-local history only applies to a project that still exists, while the unchanged top-level `Snapshot.done_tasks` retains all completed tasks for compatibility.

- [ ] **Step 4: Run the focused storage tests**

  Run:

  ```bash
  ./.venv/bin/python -m pytest app/tests/test_storage.py -q
  ```

  Expected: PASS, including the new test and the existing snapshot, completion, and undo tests.

- [ ] **Step 5: Commit the backend contract**

  ```bash
  git add app/core/models.py app/core/storage.py app/tests/test_storage.py
  git commit -m "feat: include completed tasks in project snapshots"
  ```

### Task 2: Render permanent project-local completed history

**Files:**
- Modify: `web/lib/api.ts:167-178`
- Modify: `web/components/MainBoard.tsx:581-680, 928-1285`
- Create: `app/tests/test_project_completed_task_visibility.py`

**Interfaces:**
- Consumes: `ProjectSnapshot.done_tasks: Task[]`, `ProjectSnapshot.done_count: number`, existing `api.undoTask(id): Promise<Task>`, and `ProjectCard.onChange()` snapshot refresh.
- Produces: `CompletedTaskRow({ task, onChange })`, an always-visible project-local completed section, and active-only DnD/add-task behavior.

- [ ] **Step 1: Write the failing UI-contract guardrail tests**

  Create `app/tests/test_project_completed_task_visibility.py` with this complete content:

  ```python
  """Project-local completed-task visibility invariants."""
  from pathlib import Path

  ROOT = Path(__file__).parent.parent.parent
  MAINBOARD = ROOT / "web" / "components" / "MainBoard.tsx"
  API_TYPES = ROOT / "web" / "lib" / "api.ts"
  BACKEND_MODELS = ROOT / "app" / "core" / "models.py"


  def read(path: Path) -> str:
      assert path.exists(), f"Missing source file: {path}"
      return path.read_text(encoding="utf-8")


  def function_body(src: str, name: str) -> str:
      start = src.find(f"function {name}(")
      assert start >= 0, f"function {name} is missing"
      index = start + len(f"function {name}(")
      paren_depth = 1
      quote = None
      while index < len(src) and paren_depth:
          char = src[index]
          if quote:
              if char == "\\\\":
                  index += 2
                  continue
              if char == quote:
                  quote = None
          elif char in ("'", '"', "`"):
              quote = char
          elif char == "(":
              paren_depth += 1
          elif char == ")":
              paren_depth -= 1
          index += 1
      assert paren_depth == 0, f"function {name} parameters are not balanced"
      while index < len(src) and src[index].isspace():
          index += 1
      assert index < len(src) and src[index] == "{", f"function {name} has no body"
      body_start = index
      depth = 0
      quote = None
      index = body_start
      while index < len(src):
          char = src[index]
          if quote:
              if char == "\\\\":
                  index += 2
                  continue
              if char == quote:
                  quote = None
          elif char in ("'", '"', "`"):
              quote = char
          elif char == "{":
              depth += 1
          elif char == "}":
              depth -= 1
              if depth == 0:
                  return src[body_start + 1:index]
          index += 1
      raise AssertionError(f"function {name} body is not balanced")


  def test_project_snapshot_contract_exposes_done_tasks():
      assert "done_tasks: list[Task]" in read(BACKEND_MODELS)
      assert "done_tasks: Task[];" in read(API_TYPES)


  def test_project_card_keeps_active_work_before_completed_history():
      body = function_body(read(MAINBOARD), "ProjectCard")
      assert "const activeTasks = project.tasks" in body
      assert "const completedTasks = project.done_tasks" in body
      assert "const totalTaskCount = activeTasks.length + completedTasks.length" in body
      assert "{doneCount}" in body
      assert "/{totalTaskCount}" in body
      assert "items={activeTasks.map((t) => t.id)}" in body
      assert "{completedTasks.length > 0 && (" in body
      assert "<CompletedTaskRow" in body
      assert body.index("添加任务") < body.index("completedTasks.length > 0")


  def test_completed_rows_only_offer_confirmed_task_undo():
      body = function_body(read(MAINBOARD), "CompletedTaskRow")
      assert "task.completed_at" in body
      assert "line-through" in body
      assert "api.undoTask(task.id)" in body
      assert "confirm(`撤销" in body
      assert "onChange()" in body
      assert "SortableTaskRow" not in body
      assert "onRequestComplete" not in body


  def test_legacy_global_completed_view_is_removed():
      assert "function LegacyCompletedTaskView" not in read(MAINBOARD)
  ```

- [ ] **Step 2: Run the guardrail tests and verify they fail before the UI change**

  Run:

  ```bash
  ./.venv/bin/python -m pytest app/tests/test_project_completed_task_visibility.py -v
  ```

  Expected: FAIL because TypeScript has no `done_tasks` field, `ProjectCard` does not define the active/completed aliases, and `LegacyCompletedTaskView` still exists.

- [ ] **Step 3: Mirror the API contract and implement the card regions**

  In `web/lib/api.ts`, add the required field to `ProjectSnapshot` directly after `tasks`:

  ```ts
  tasks: Task[];
  done_tasks: Task[];
  ```

  In `MainBoard.tsx`, delete the entire `LegacyCompletedTaskView` function. It is dead global UI and must not be moved or rendered elsewhere.

  Add a `CompletedTaskRow` function near `SortableTaskRow`, using only task display and undo behavior:

  ```tsx
  function CompletedTaskRow({ task, onChange }: { task: Task; onChange: () => void }) {
    const undo = async () => {
      if (!confirm(`撤销「${task.title}」的完成状态？任务会恢复到进行中。`)) return;
      try {
        await api.undoTask(task.id);
        onChange();
      } catch (err) {
        alert("撤销失败: " + (err instanceof Error ? err.message : err));
      }
    };

    return (
      <div className="group/completed flex items-center gap-2 px-3 py-2 text-[13px]">
        <Check size={13} className="text-success flex-shrink-0" strokeWidth={2.5} />
        <div className="min-w-0 flex-1">
          <div className="text-fg-muted line-through truncate">{task.title}</div>
          {task.completed_at && <div className="mt-0.5 text-[11px] text-fg-muted">完成于 {task.completed_at}</div>}
        </div>
        <button onClick={undo} className="text-[12px] text-fg-muted hover:text-fg transition" title="撤销完成">
          <Undo2 size={12} />
          撤销完成
        </button>
      </div>
    );
  }
  ```

  In `ProjectCard`, establish the list aliases and progress semantics before the local React state:

  ```tsx
  const activeTasks = project.tasks;
  const completedTasks = project.done_tasks;
  const doneCount = completedTasks.length;
  const totalTaskCount = activeTasks.length + completedTasks.length;
  ```

  Replace all task-list and drag calculations in `ProjectCard` with `activeTasks`. In particular, `SortableContext.items`, `activeTasks.map(...)`, the no-active-task condition, and `handleTaskDragEnd` must only use `activeTasks`.

  Replace the header count with a `totalTaskCount` check and exact progress expression:

  ```tsx
  {totalTaskCount > 0 ? (
    <span className="text-[12px] text-fg-secondary tabular-nums flex-shrink-0">
      <span className={doneCount === totalTaskCount ? "text-success" : "text-fg-secondary"}>
        {doneCount}
      </span>
      <span className="text-fg-muted">/{totalTaskCount}</span>
    </span>
  ) : (
    <span className="text-[12px] text-fg-muted flex-shrink-0">0</span>
  )}
  ```

  Keep the DnD context around only `activeTasks`, then render the existing add-task control. Immediately after that control, add a non-collapsible completed section:

  ```tsx
  {completedTasks.length > 0 && (
    <section className="mt-3 border-t border-border/40 pt-2" aria-label={`已完成 ${doneCount} 项`}>
      <div className="px-2 pb-1.5 flex items-center gap-1.5 text-[12px] font-medium text-success">
        <Check size={13} strokeWidth={2.5} />
        已完成 {doneCount} 项
      </div>
      <div className="divide-y divide-border/30 rounded-md bg-bg-secondary/40">
        {completedTasks.map((task) => (
          <CompletedTaskRow key={task.id} task={task} onChange={onChange} />
        ))}
      </div>
    </section>
  )}
  ```

  Do not add a chevron, component state, `hidden`, or a collapse/expand label to this section. Do not wrap `CompletedTaskRow` in `SortableContext` or pass it `onRequestComplete`.

- [ ] **Step 4: Run focused guardrails and TypeScript validation**

  Run:

  ```bash
  ./.venv/bin/python -m pytest app/tests/test_project_completed_task_visibility.py app/tests/test_drag_reorder_invariants.py app/tests/test_complete_path_invariants.py -q
  cd web && npx tsc --noEmit
  ```

  Expected: all selected pytest tests PASS and TypeScript exits 0 with no diagnostics. If the static test's function parser fails on a TypeScript syntax detail, fix only the parser in the new test; do not weaken any behavioral assertion.

- [ ] **Step 5: Commit the frontend feature and its guardrails**

  ```bash
  git add web/lib/api.ts web/components/MainBoard.tsx app/tests/test_project_completed_task_visibility.py
  git commit -m "feat: show completed tasks in project cards"
  ```

## Final Verification and Handoff

- [ ] **Step 1: Inspect ownership before the final test run**

  Run:

  ```bash
  git status --short
  git diff -- web/components/ProjectEmojiPicker.tsx web/app/globals.css
  ```

  Expected: the feature commits contain only the six planned files; the user's existing emoji-tooltip modifications remain unstaged and unaltered.

- [ ] **Step 2: Run the required regression commands**

  Run:

  ```bash
  ./.venv/bin/python -m pytest app/tests/ -q
  cd web && npx tsc --noEmit
  ```

  Expected: both commands exit 0. Do not substitute `next build`.

- [ ] **Step 3: Perform manual light/dark verification**

  With a project containing one active task and at least two completed tasks:

  1. Expand the project in light theme; verify the header is `2/3`, the active row is first, and all completed rows are visible below the add-task control.
  2. Confirm the completed header reads `已完成 2 项`, has no chevron or expand/collapse control, and each row has muted strikethrough text plus a completion date.
  3. Drag the active task; confirm a completed row cannot become a drag target.
  4. Use `撤销完成`, accept the confirmation, and verify the task returns to the active region and progress becomes `1/3`.
  5. Repeat steps 1-2 in dark theme; verify borders, muted text, success cue, and button remain readable.

- [ ] **Step 4: Deliver evidence**

  Report the changed-file summary, exact commands and exit codes, acceptance-criteria checklist, manual-verification results, intentional deviations, and both feature commit hashes. Explicitly state that task completion still creates achievements and that user-owned emoji-tooltip files were neither edited nor staged.

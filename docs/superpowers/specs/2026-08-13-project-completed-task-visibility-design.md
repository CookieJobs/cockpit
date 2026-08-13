# Project-Local Completed Task Visibility — Design

## Decision

**Approved direction:** each expanded project card is a complete work record:
active tasks appear first and completed tasks remain visibly below them in a
permanent completed section. The completed section is never collapsed.

Cockpit's achievement library remains the source for career-ready statements;
the project card remains the human-readable record of the work that produced
those assets. Completing a task must therefore mean “settled and visibly
credited in its project”, not “removed from the project”.

## Problem and root cause

The backend already preserves a completed task: `complete_task` changes its
status to `已完成` and records `completed_at`; it does not delete the task.
`build_snapshot` also calculates a project-level `done_count` and returns the
global `done_tasks` collection.

The project-card snapshot, however, currently contains active tasks only. The
card renders only that active list, and derives its displayed completed count
from that same list. Thus a project with one completed task and one active task
can misleadingly show `0/1`, while its completed task is absent from the very
project in which it was completed. A legacy global completed-task view exists,
but it is not an appropriate replacement for a project-local work record.

## User-facing behavior

### Project card composition

When a project is expanded, it renders exactly two ordered task regions:

1. **活动任务** — all `未开始` and `进行中` tasks, in the existing project
   `sort_order` sequence, with the existing drag/drop, inline editing, due date,
   checklist, and completion-entry behavior.
2. **已完成** — all `已完成` tasks from that same project, immediately below the
   active region. This region is always visible whenever it has at least one
   task; it has no collapse control.

The completed region is intentionally secondary but readable:

- its header states `已完成 N 项` and includes a success/check cue;
- each row shows its title with a muted strikethrough and its completion date;
- its visual treatment must make it distinct from active work without hiding it;
- an empty completed region is omitted rather than rendering an empty-state
  message.

Adding a new task remains at the end of the active region, above the completed
region. It must never appear below completed history.

### Real project progress

The project header displays `完成数 / 总任务数`:

- completed count is the number of completed tasks for the project;
- total is active plus completed tasks for the project;
- `0` is shown only when the project has no tasks at all;
- e.g. one completed and one active task displays `1/2`.

This is project progress, not checklist progress and not a count of career-ready
achievements. A task that creates a `pending` or `needs_data` achievement is
still a completed task and counts as completed here.

### Completed-task action

Each completed row offers the existing explicit **撤销完成** action. On
confirmation it uses the existing task-id undo API, returns the task to the
active region, and refreshes progress. Its original task fields (priority,
due date, checklist, description, created date, and sort order) remain intact.

Completed rows are history, not active work:

- they must not be focus candidates or affect the active-task drag/drop context;
- they may not expose a second “complete” entry point;
- they do not need inline priority/due/checklist editing in this scope.

## Data and architecture contract

Extend the existing snapshot contract rather than issuing per-project task
requests or duplicating task state:

- `ProjectSnapshot.tasks` continues to mean active tasks only, preserving its
  existing consumers and action-focused semantics;
- add `ProjectSnapshot.done_tasks: list[Task]`, containing only completed tasks
  belonging to that project, sorted by `completed_at` descending with a stable
  deterministic tie-breaker;
- retain `ProjectSnapshot.done_count` and make it equal
  `len(ProjectSnapshot.done_tasks)` for normal projects;
- retain top-level `Snapshot.done_tasks` unchanged for backward compatibility
  during this change, but stop rendering the orphaned global completed-task view
  in `MainBoard`.

`build_snapshot` remains the sole backend grouping boundary. It reads all tasks
once, derives active/completed partitions once, supplies each project's active
and completed lists, and does not change database schema, task completion,
achievement creation, or undo persistence semantics.

## Scope boundaries

### In scope

- `ProjectSnapshot` backend/frontend contract and snapshot grouping.
- Project-card progress calculation and expanded-card completed-task region.
- Reusing the existing task-id undo API from the project-local completed row.
- Regression tests for snapshot membership/order, progress semantics, rendering
  boundaries, and undo refresh behavior.

### Explicitly out of scope

- Changing `complete_task`, `undo_completion`, achievement readiness, CV
  generation, or report inclusion rules.
- New filters, archives, pagination, search, a second completed-task database
  model, or new API endpoints.
- Making completed rows draggable or editable inline.
- Changing the global task list API default (`include_completed=False`).
- Modifying `ProjectEmojiPicker.tsx`, `web/app/globals.css`, or any currently
  uncommitted emoji-tooltip work.

## Interaction and visual constraints

- Active tasks must remain visually and spatially first; completed history begins
  only after the active task list and add-task control.
- Do not introduce another independently expandable/collapsible panel for
  completed history.
- Reuse semantic theme tokens and existing muted/success styles. No hard-coded
  colours or theme-specific forks.
- Preserve the app's existing confirmation before undo; no destructive action is
  allowed from a completed row without that confirmation.
- Retire the unmounted `LegacyCompletedTaskView` rather than keeping duplicate,
  dead UI logic. The retained top-level snapshot field is data compatibility, not
  a reason to keep a second homepage history display.

## Acceptance criteria

1. A completed task remains available in the project snapshot and appears in the
   expanded project card below all active tasks.
2. The completed region is permanently visible when non-empty, labelled with its
   count, and omitted when empty; it cannot be collapsed.
3. The header shows completed/total using project snapshot data, so one active
   plus one completed task displays `1/2`.
4. The active drag/drop context and add-task control contain active tasks only;
   completed rows cannot be dragged or accidentally re-completed.
5. A completed row shows a completion date and can explicitly undo through the
   existing task-id undo route; after refresh it returns to active work and
   progress updates.
6. Existing task retention, achievement creation, readiness, and global snapshot
   compatibility remain unchanged.
7. Focused regression tests cover data partitioning/order and the project-card
   UI contract. `./.venv/bin/python -m pytest app/tests/ -q` and
   `cd web && npx tsc --noEmit` pass. Do not run `next build`.
8. Manual verification includes a project with mixed active/completed tasks in
   both themes and confirms active-first ordering, readable completed history,
   correct `1/2` progress, and undo restoration.

## Existing-worktree constraint

The worktree contains user-owned uncommitted tooltip changes in
`web/components/ProjectEmojiPicker.tsx` and `web/app/globals.css`, plus unrelated
untracked files. The implementer must inspect and preserve them, must not stage
them, and must report a conflict rather than resolving it by overwriting them.

## Required implementer evidence

The execution handoff must include changed-file summary, exact commands and exit
codes, an acceptance-criteria checklist with evidence, manual verification
results, all intentional deviations, and a commit that includes only files
owned by this feature.

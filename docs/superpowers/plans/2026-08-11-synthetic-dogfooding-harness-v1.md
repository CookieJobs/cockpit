# Synthetic Dogfooding Harness v1 — Implementation Plan

> **For the Cockpit AI CTO:** Execute this plan on `main`, in the listed order. The
> user explicitly authorized direct, autonomous iteration on the main branch.

**Goal:** Make four reproducible synthetic work personas exercise Cockpit's real
task-completion and achievement APIs against isolated SQLite databases, then
produce evidence-grounded weekly and monthly report artefacts plus a deterministic
review summary.

**Architecture:** Persona fixtures describe only auditable work events and their
expected evidence. A Python runner replays them through FastAPI's public API in a
fresh temporary database per persona. A report adapter consumes the stored,
`ready`-only achievement export, and a deterministic reviewer checks coverage,
fact grounding, and recovery behaviour. The runner writes versioned artefacts
outside the repository by default; it never uses a developer's real Cockpit DB.

**Tech Stack:** Python 3.11+, FastAPI test client, SQLite, pytest, TypeScript
report-template adapter, JSON fixtures.

---

## Task 1: Define the synthetic-user data contract and auditable fixtures

**Files:**

- Create: `app/harness/synthetic/__init__.py`
- Create: `app/harness/synthetic/models.py`
- Create: `app/harness/synthetic/fixtures.py`
- Create: `app/harness/fixtures/synthetic_dogfooding_v1.json`
- Test: `app/tests/harness/test_synthetic_fixtures.py`

**Step 1: Write the failing tests.**

Cover loading a fixture, stable persona IDs, four distinct roles, four weeks of
events, and rejection of an event whose CV claim contains an unsupported fact.
The test must assert that every completion includes explicit fact anchors and a
quality expectation (`ready` or `needs_data`).

**Step 2: Run the focused test to verify red.**

Run `.venv312/bin/pytest app/tests/harness/test_synthetic_fixtures.py -v`.

**Step 3: Implement the smallest contract.**

Use frozen dataclasses or Pydantic models for `Persona`, `WorkEvent`, and
`SyntheticDataset`. Keep event fields constrained to work facts that can be
submitted through the existing completion API: project, title, due date, outcome,
CV statement, reflection, follow-up answers, and expected readiness. Validate that
every number, percentage, date-range, or named deliverable in `cv` occurs in the
combined supplied evidence. Give fixtures no real person/company data.

The v1 fixture contains: a B2C product manager, engineering team lead, growth
operator, and independent designer. Each has enough dated events to exercise four
weekly windows; at least one event per persona is intentionally `needs_data` and
therefore must not leak to output.

**Step 4: Run focused tests to verify green.**

Run `.venv312/bin/pytest app/tests/harness/test_synthetic_fixtures.py -v`.

**Step 5: Commit.**

`git add app/harness/synthetic app/harness/fixtures/synthetic_dogfooding_v1.json app/tests/harness/test_synthetic_fixtures.py && git commit -m "feat(harness): add synthetic dogfooding fixtures"`

## Task 2: Replay events through a fresh public API boundary per persona

**Files:**

- Create: `app/harness/synthetic/runner.py`
- Create: `app/scripts/run_synthetic_dogfooding.py`
- Modify: `Makefile`
- Test: `app/tests/harness/test_synthetic_runner.py`

**Step 1: Write failing runner tests.**

Use temporary databases and FastAPI's `TestClient`. Assert that each run creates
only its own projects/tasks/achievements, submits task creation and completion via
the public API, preserves event completion dates for weekly windows, and refuses to
write under `~/.cockpit` or an existing production database path.

**Step 2: Run the focused test to verify red.**

Run `.venv312/bin/pytest app/tests/harness/test_synthetic_runner.py -v`.

**Step 3: Implement replay isolation.**

Create one temporary SQLite database per persona. Reset the test application's
storage engine only within the runner's controlled context; submit projects/tasks
and task completion through API requests, never ORM or SQL fixture inserts.
Introduce an explicit time seam solely in the runner so events get their fixture
dates without changing production completion semantics. Export a compact
achievement snapshot after the API replay, including readiness and source evidence.

Add `make synthetic-dogfood` which writes results to a supplied directory or a
new temporary directory and prints its location. Do not add a default that can
write to the user's live Cockpit DB.

**Step 4: Run focused tests to verify green.**

Run `.venv312/bin/pytest app/tests/harness/test_synthetic_runner.py -v`.

**Step 5: Commit.**

`git add app/harness/synthetic/runner.py app/scripts/run_synthetic_dogfooding.py Makefile app/tests/harness/test_synthetic_runner.py && git commit -m "feat(harness): replay synthetic work through public APIs"`

## Task 3: Generate report artefacts through the existing report template layer

**Files:**

- Create: `web/scripts/generate-synthetic-report.mjs`
- Modify: `app/harness/synthetic/runner.py`
- Test: `app/tests/harness/test_synthetic_reports.py`
- Test: `web/scripts/test-synthetic-report.mjs`

**Step 1: Write failing tests.**

Export one persona snapshot with both `ready` and `needs_data` achievement data.
Assert weekly reports cover each of the four fixture windows, the monthly output
covers the full window, and none contains a non-ready CV claim.

**Step 2: Run tests to verify red.**

Run the Python test and
`node --experimental-strip-types web/scripts/test-synthetic-report.mjs`.

**Step 3: Implement a narrow adapter.**

The Node script accepts a JSON snapshot and explicit date window, filters to
`ready` entries defensively, and calls the existing `web/lib/templates.ts`
composition path. It returns plain Markdown/JSON only. The Python runner invokes
it and persists weekly and full-window (“monthly coverage”) outputs in the run
artefact directory. This is intentionally not a claim that the final dedicated
monthly template has shipped.

**Step 4: Run focused tests to verify green.**

Repeat both test commands.

**Step 5: Commit.**

`git add web/scripts/generate-synthetic-report.mjs web/scripts/test-synthetic-report.mjs app/harness/synthetic/runner.py app/tests/harness/test_synthetic_reports.py && git commit -m "feat(harness): generate synthetic report artefacts"`

## Task 4: Add deterministic review and release-gate integration

**Files:**

- Create: `app/harness/synthetic/review.py`
- Modify: `app/harness/synthetic/runner.py`
- Modify: `app/harness/project_gate.py`
- Modify: `docs/harness/capabilities-v1.yaml`
- Test: `app/tests/harness/test_synthetic_review.py`
- Test: `app/tests/harness/test_project_gate.py`

**Step 1: Write failing tests.**

Test the reviewer’s calculation of completion rate, readiness rate, weekly/monthly
coverage, unsupported-fact findings, non-ready leakage, and recovery rate. Assert
that an unsupported output fact or non-ready output claim is P0 and fails the
synthetic harness capability check.

**Step 2: Run focused tests to verify red.**

Run `.venv312/bin/pytest app/tests/harness/test_synthetic_review.py app/tests/harness/test_project_gate.py -v`.

**Step 3: Implement deterministic review.**

Create a machine-readable `review.json` and readable `weekly-review.md` from each
run. The aggregation must clearly label data as synthetic and include limitations:
it measures workflow and evidence integrity, not user adoption or product-market
fit. Register a `synthetic_dogfooding` capability as advisory until it has stable
fixtures and is independently reviewed; `make project-gate` must still validate
its contract when the capability is enabled.

**Step 4: Run focused tests to verify green.**

Repeat the focused suite.

**Step 5: Commit.**

`git add app/harness/synthetic/review.py app/harness/synthetic/runner.py app/harness/project_gate.py docs/harness/capabilities-v1.yaml app/tests/harness/test_synthetic_review.py app/tests/harness/test_project_gate.py && git commit -m "feat(harness): review synthetic dogfooding runs"`

## Task 5: Full regression, run artefact, and CTO decision memo

**Files:**

- Create: `docs/harness/reports/2026-08-11-synthetic-dogfooding-baseline.md`
- Modify: `docs/harness/README.md`
- Modify: `docs/lessons/04-testing-strategy.md` (only if a reusable lesson emerges)

**Step 1: Execute the harness.**

Run `make synthetic-dogfood` to produce a fresh local artefact directory. Inspect
the generated review and report files; do not commit generated user-like data or
temporary databases.

**Step 2: Run required regression.**

Run `.venv312/bin/pytest app/tests/ -v`, `cd web && npx tsc --noEmit`, the
report-template script test, and `make project-gate`. Never run `next build` while
the dev server may be active.

**Step 3: Write the decision memo.**

Record the run identifier, metrics, P0/P1 issues, known limits, and the next CTO
decision. Explicitly separate synthetic evidence from the GOAL.md real-dogfooding
thresholds (two weeks, 20 real achievements, adoption evidence).

**Step 4: Self-review before final commit.**

Scan the diff for TODO/FIXME/placeholders and direct production DB paths. Re-read
the public API replay boundary and the ready-only filtering contract.

**Step 5: Commit.**

`git add docs/harness/README.md docs/harness/reports/2026-08-11-synthetic-dogfooding-baseline.md docs/lessons/04-testing-strategy.md && git commit -m "docs(harness): record synthetic dogfooding baseline"`

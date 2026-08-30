# Core Loop Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收敛 Cockpit 为“任务完成 → 有证据的成就 → 用户确认 → ready-only 输出”的可信本地闭环，同时完成 Spec 规定的产品减法、可携带性和两周真实自用验证。

**Architecture:** 将 `storage` 作为唯一的 readiness 判定和写入边界；Web、聊天和 MCP 只能提交事实与确认，不能声明最终 `ready`。所有正式输出经共享的 ready-only 查询（Phase 1）以及确定性 Composer（Phase 3）读取成就库。数据库迁移、备份、导入/导出和危险操作均在本地、可恢复、事务化边界内完成。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy async + SQLite、Pydantic v2、Next.js 15 / TypeScript、SWR、pytest、Node 类型检查。

## Global Constraints

- 严格按 Phase 1 → Phase 4 执行；不得以视觉改名代替数据流、readiness 或安全边界改造。
- P0-1 至 P0-5 每项均先新增可运行且确实失败的行为回归测试，再写最小实现；不得用放宽 provenance guardrail 换取通过率。
- Web、聊天、MCP、存储、模板、SSE 与持久化遵循同一事实/readiness 契约；调用方传 `cv_status=ready` 不构成授权。
- 任何正式周报、月报、述职、CV、复制、下载、导出路径只读取 `ready` achievement；成就库与补证页可读取非 ready 条目。
- 不删除或覆盖用户职业资产、聊天、trace、feedback、追问和答案；schema 迁移、导入、危险删除前均创建可恢复备份，并在隔离临时目录测试。
- 保留 `tags_json` 历史列并在导入/导出中原样传输，但从 UI、DTO 和新逻辑移除 tags；删除 `Task.draft` 前备份且历史 draft task 保留为未完成普通任务。
- LLM/网络不可用时，CRUD、查看、草稿保存、本地模板输出、备份导出继续可用；失败必须可见，不能伪造成功或假 0。
- 不运行 `next build`（尤其 dev server 运行时）；前端验证使用 `cd web && npx tsc --noEmit`。
- 每个 Phase 结束前运行该 Phase 指定测试与受影响既有测试；工作树只应包含当前 Phase 的文件，再以一个独立 commit 提交。禁止修改既有未提交文件。
- 实施前再次阅读 `.ai/AI_CTO.md`、`docs/GOAL.md`、`docs/architecture/ai-native-architecture-v1.md`、`docs/harness/achievement-distillation-harness-v1.md` 及相关 lessons；实现时以这些文件和本 Spec 为准。

## Locked Interfaces and State Rules

These names are the cross-task contract. Do not rename them without updating every consumer and its tests in the same task.

```python
# app/core/storage.py
@dataclass(frozen=True)
class ReadinessDecision:
    status: CVStatus
    unmet_reasons: list[str]

def derive_achievement_readiness(
    *, task_title: str, outcome: str, cv: str,
    follow_up_questions: list[str], follow_up_answers: dict[str, str],
    requested_draft: bool, final_cv_confirmed: bool,
    provenance: dict[str, object], cv_regenerated_after_answers: bool,
) -> ReadinessDecision:
    """Return a server-derived output status and every unmet prerequisite."""

async def list_output_ready_achievements(
    *, since: date | None = None, until: date | None = None,
    project_id: str | None = None,
) -> list[Achievement]:
    """Return only output-eligible achievements inside the supplied window."""

async def save_follow_up_answers(aid: str, answers: dict[str, str]) -> Achievement | None:
    """Persist structured non-empty answer drafts without changing readiness."""

async def resolve_achievement(
    aid: str, *, answers: dict[str, str], cv: str,
    distillation_trace_id: str | None = None,
) -> Achievement | None:
    """Atomically persist answers, confirmed final CV, trace and derived status."""
```

```python
# app/api/achievements.py
class ResolveAchievementRequest(BaseModel):
    answers: dict[str, str]
    cv: str = Field(min_length=1, max_length=2000)
    distillation_trace_id: str | None = None

@router.post("/{aid}/resolve")
async def resolve_achievement(aid: str, data: ResolveAchievementRequest) -> dict:
    """Persist the confirmed regenerated CV and return actual readiness/reasons."""
```

`requested_draft=True` is the only way a write may become `pending`. All other unsatisfied requirements become `needs_data`. `resolve_achievement` is the explicit user confirmation boundary for its supplied final CV; saving answers alone never changes an achievement to `ready`.

---

## Phase 1 — Authenticity and Data Safety

**Phase acceptance:** P0-1 … P0-5 have test-first proof, all formal output entries are ready-only, no CoT reaches SSE/persistence/DOM, and page data failures are distinct from empty results. No Phase 2 product removals are included in this commit.

### Task 1: P0-5 Resolve Data Directory and Migrate the Misplaced Database Safely

**Files:**
- Create: `app/tests/test_data_directory_migration.py`
- Modify: `app/core/config.py`
- Modify: `app/main.py` only if startup needs to expose/hold a recoverable migration conflict state
- Modify: `.env.example`, `README.md` only if they currently document the unresolved path (defer broad wording alignment to Phase 4)

**Interfaces:**
- Consumes: `Settings.cockpit_data_dir`, `Settings.get_database_url()`.
- Produces: `Settings.resolved_data_dir() -> Path`, `Settings.data_recovery_state() -> DataRecoveryState`, and an idempotent startup migration before the database engine is opened.

- [ ] **Step 1: Write failing isolated-path tests before changing configuration.**

```python
def test_resolved_data_dir_expands_home_and_is_absolute(monkeypatch, tmp_path):
    monkeypatch.setenv("COCKPIT_DATA_DIR", "~/cockpit-test")
    settings = Settings(_env_file=None)
    assert settings.resolved_data_dir().is_absolute()
    assert "~" not in str(settings.resolved_data_dir())

def test_migrates_only_misplaced_database_and_keeps_timestamped_backup(tmp_path):
    cwd, home = tmp_path / "cwd", tmp_path / "home"
    misplaced = cwd / "~" / ".cockpit" / "cockpit.db"
    correct = home / ".cockpit" / "cockpit.db"
    create_sqlite_fixture(misplaced, projects=1)
    state = migrate_misplaced_database(cwd=cwd, target=correct)
    assert state.kind == "migrated"
    assert sqlite_integrity_ok(correct)
    assert list(misplaced.parent.glob("cockpit.db.migrated-*.bak"))

def test_different_databases_enter_conflict_without_writing_either(tmp_path):
    create_sqlite_fixture(tmp_path / "cwd/~/.cockpit/cockpit.db", projects=1)
    create_sqlite_fixture(tmp_path / "home/.cockpit/cockpit.db", projects=2)
    before = hashes_of_both_databases(tmp_path)
    state = migrate_misplaced_database(cwd=tmp_path / "cwd", target=tmp_path / "home/.cockpit/cockpit.db")
    assert state.kind == "conflict"
    assert hashes_of_both_databases(tmp_path) == before
```

- [ ] **Step 2: Run the new tests and record red status.**

Run: `.venv312/bin/pytest app/tests/test_data_directory_migration.py -q`  
Expected: FAIL because neither resolved path nor migration/conflict helper exists.

- [ ] **Step 3: Implement the narrow migration boundary.**

```python
def resolved_data_dir(self) -> Path:
    return self.cockpit_data_dir.expanduser().resolve()

def migrate_misplaced_database(*, cwd: Path, target: Path) -> DataRecoveryState:
    # compare SQLite-readable files by SHA-256; copy to target's temporary sibling;
    # fsync/verify/open it; atomically replace only when target is absent;
    # rename original to a timestamped .bak; never merge or delete either source.
    """Return migrated/equal/conflict/failed state without deleting either database."""
```

Implement all four Spec outcomes: absent misplaced DB is a no-op; only misplaced copies safely; equal dual copies select correct target without deletion; unequal copies set a recovery conflict that blocks writes and exposes both paths. On any copy/validation error, retain original files and report an actionable error instead of creating an empty DB. Keep legacy `~/.shiguang` migration compatible and ordered after the new target is resolved.

- [ ] **Step 4: Make startup and diagnostics use the one resolved value.**

`get_database_url()` must call `resolved_data_dir()` before `mkdir`, database URL construction, log output, settings display, and migration detection. Add a write guard in the shared session/write entry path when recovery state is `conflict` or `failed`; read-only diagnostics remain available.

- [ ] **Step 5: Run focused and existing configuration tests.**

Run: `.venv312/bin/pytest app/tests/test_data_directory_migration.py app/tests/test_storage.py -q`  
Expected: PASS; test temp directories only, no access to the real `~/.cockpit`.

### Task 2: P0-1 Create the Unified Readiness/Resolve Transaction

**Files:**
- Create: `app/tests/test_achievement_readiness_resolution.py`
- Modify: `app/core/models.py`
- Modify: `app/core/storage.py`
- Modify: `app/api/achievements.py`
- Modify: `app/api/tasks.py`
- Modify: `app/harness/feedback.py` only to add first-completion feedback without duplicating trace records

**Interfaces:**
- Consumes: Task/project snapshots, `follow_up_questions_json`, structured answers, existing `evaluate_l1` provenance result, trace id.
- Produces: `ReadinessDecision`, `/api/achievements/{aid}/resolve`, and completion responses carrying persisted `cv_status` plus `unmet_reasons`.

- [ ] **Step 1: Write failing behavioral tests for every readiness transition.**

```python
async def test_answer_follow_ups_saves_partial_answers_without_promoting_ready(client, achievement):
    response = await client.patch(f"/api/achievements/{achievement.id}/follow_ups", json={"answers": {"0": "覆盖 20 个用户"}})
    assert response.status_code == 200
    assert response.json()["cv_status"] == "needs_data"

async def test_all_answers_without_regenerated_confirmed_cv_remains_needs_data(client, achievement):
    await client.patch(f"/api/achievements/{achievement.id}/follow_ups", json={"answers": {"0": "20 个用户"}})
    stored = await storage.get_achievement(achievement.id)
    assert stored.cv_status is CVStatus.NEEDS_DATA

async def test_resolve_promotes_only_when_new_cv_confirmed_and_guardrail_passes(client, achievement):
    response = await client.post(f"/api/achievements/{achievement.id}/resolve", json={
        "answers": {"0": "影响 20 个用户"}, "cv": "修复登录鉴权问题，恢复 20 名用户登录", "distillation_trace_id": "trace_1"})
    assert response.json()["cv_status"] == "ready"
    assert response.json()["unmet_reasons"] == []

async def test_resolve_rejects_unsupported_number_entity_and_ownership(client, achievement):
    response = await client.post(f"/api/achievements/{achievement.id}/resolve", json={
        "answers": {"0": "修复登录问题"}, "cv": "主导 5 人团队修复登录问题，使转化率提升 30%"})
    assert response.json()["cv_status"] == "needs_data"
    assert "存在无来源事实" in response.json()["unmet_reasons"]
```

- [ ] **Step 2: Run the new readiness tests to prove P0-1 is red.**

Run: `.venv312/bin/pytest app/tests/test_achievement_readiness_resolution.py -q`  
Expected: FAIL because current `answer_follow_ups` writes `ready` and `/resolve` does not exist.

- [ ] **Step 3: Replace the scattered status checks with one deterministic decision function.**

Implement `derive_achievement_readiness()` in `storage`, evaluating all Spec 6.2 conditions: trimmed outcome length, title fallback, every non-empty question answered, a CV regenerated after answers, explicit final-CV confirmation at resolve, and P0 provenance result. Return canonical human-facing reasons such as `缺少结果描述`, `追问未答`, `CV 尚未吸收补充证据`, `CV 尚未确认`, `存在无来源事实`; derive them rather than accepting user input.

- [ ] **Step 4: Split answer-draft from atomic resolve.**

```python
async def save_follow_up_answers(aid: str, answers: dict[str, str]) -> Achievement | None:
    # merge only non-empty structured answers; preserve status unless it is invalid
    return await _save_answer_draft(aid, answers)

async def resolve_achievement(aid: str, *, answers: dict[str, str], cv: str,
                              distillation_trace_id: str | None = None) -> Achievement | None:
    async with get_session() as session:
        # locate achievement, merge answers, replace CV and trace id,
        # compute guardrail + readiness, persist all fields in one transaction.
        return await _resolve_in_open_session(session, aid, answers, cv, distillation_trace_id)
```

The existing PATCH endpoint becomes “save answer draft” and cannot promote state. The new POST is the only follow-up resolution writer. Make `complete_task` call the same function/rules (with `requested_draft` only for the secondary button). Never trust API, chat, or MCP supplied `ready`.

- [ ] **Step 5: Record feedback at both candidate-final confirmation points.**

When a completion has a trace and the user confirms/edits its candidate CV, persist a local feedback record linked to the same trace, labelled `direct_accept`, `light_edit`, `rewrite`, `draft`, or `abandoned` according to deterministic comparison/action rules. Do not create cloud analytics or a visible scorecard.

- [ ] **Step 6: Run readiness, API completion, follow-up, harness, and storage tests.**

Run: `.venv312/bin/pytest app/tests/test_achievement_readiness_resolution.py app/tests/test_api_answer_follow_ups.py app/tests/test_api_complete_task.py app/tests/test_storage.py app/tests/harness/test_feedback_persistence.py -q`  
Expected: PASS; include a regression proving old CV plus complete answers cannot become ready.

### Task 3: P0-3 Make Distillation Suggestions Carry Questions, Evidence, and Freshness Through Completion

**Files:**
- Create: `app/tests/test_complete_modal_suggestion_flow.py` (source-level only for browser race invariants) and extend API behavior tests in `app/tests/test_api_polish_cv.py`
- Modify: `app/api/llm.py`
- Modify: `web/lib/api.ts`
- Modify: `web/components/CompleteTaskModal.tsx`
- Modify: `web/components/Toast.tsx` and the MainBoard completion callback as needed

**Interfaces:**
- Consumes: `PolishCvResponse { cv, polished, follow_up_questions, trace_id, guardrail_results }`.
- Produces: one current suggestion request token, structured questions passed to `complete_task`, and a completion response-driven toast/cache update.

- [ ] **Step 1: Write tests that fail against the automatic-suggestion path.**

```python
def test_auto_suggestion_persists_questions_not_only_cv():
    source = read("web/components/CompleteTaskModal.tsx")
    assert "setFollowUpQuestions(res.follow_up_questions" in auto_suggestion_callback(source)

async def test_completion_with_auto_generated_questions_is_not_ready(client, task):
    result = await client.post(f"/api/tasks/{task.id}/complete", json={
        "outcome": "完成登录问题排查并修复", "cv": "修复登录问题",
        "follow_up_questions": ["影响了多少用户？"]})
    assert result.json()["cv_status"] == "needs_data"
```

Also test that an older delayed request cannot overwrite a newer outcome’s CV/questions/trace and that an unavailable LLM supplies an editable fallback but not `ready`.

- [ ] **Step 2: Run the P0-3 tests to prove red.**

Run: `.venv312/bin/pytest app/tests/test_complete_modal_suggestion_flow.py app/tests/test_api_polish_cv.py -q`  
Expected: FAIL because auto callback currently stores only CV and trace.

- [ ] **Step 3: Extend the polishing response and trace consistently.**

Keep `<think>` stripping before JSON fallback. Return parsed questions, trace id, and guardrail summary from the same response. Add a refinement request shape accepting `task`, `project`, outcome, reflection, structured `questions`, and `answers`; it must retain answer provenance rather than concatenate questions into outcome.

- [ ] **Step 4: Rework `CompleteTaskModal` to one suggestion flow.**

Use a monotonic request id plus `AbortController` (or equivalent current-request check) on each 1.5-second debounced outcome change. Mark old suggestions stale, atomically update `cv`, `followUpQuestions`, trace and guardrail result only for the newest request, show one editable candidate, render each question with an independent answer input, and expose “重新生成” only after a candidate exists or auto generation failed. The secondary “暂存草稿” sends `requested_draft`; the primary action sends all structured questions/answers and lets the server return actual state.

- [ ] **Step 5: Use server response for UI state.**

Change `onSave` to return `Achievement`; invalidate/update snapshot from that object. Toast exactly one of `已沉淀，可直接使用`, `已保存，待补证据`, or `已暂存草稿`. Never increment ready count optimistically.

- [ ] **Step 6: Run focused UI invariant/API tests.**

Run: `.venv312/bin/pytest app/tests/test_complete_modal_suggestion_flow.py app/tests/test_complete_modal_minimal_invariants.py app/tests/test_completion_toast_invariants.py app/tests/test_api_complete_task.py app/tests/test_api_polish_cv.py -q`  
Expected: PASS with auto and manual generation following the same questions contract.

### Task 4: P0-2 Establish the Ready-Only Output Read Boundary Across Web, Chat, and MCP

**Files:**
- Create: `app/tests/test_ready_only_output_boundaries.py`
- Modify: `app/core/storage.py`
- Modify: `app/llm/tools.py`
- Modify: `app/api/achievements.py` only for compatible output-specific query use
- Modify: `web/app/report/page.tsx`, `web/lib/templates.ts`, `web/lib/api.ts`
- Modify: `app/tests/constitution/test_output_and_write_boundaries.py`, `app/tests/test_report_workspace_invariants.py`

**Interfaces:**
- Consumes: `list_output_ready_achievements()`.
- Produces: a single status-filtered selection operation for all current formal output code; Phase 3 later centralizes formatting in Composer.

- [ ] **Step 1: Write sentinel behavior tests before filtering implementation.**

```python
async def test_web_and_chat_outputs_emit_only_ready_sentinel(isolated_db, client):
    await seed_achievements(isolated_db, [
        ("READY_SENTINEL", "ready"),
        ("NEEDS_DATA_SENTINEL", "needs_data"),
        ("PENDING_SENTINEL", "pending"),
    ])
    chat = await run_tool("generate_weekly_report")
    report = await client.get("/api/achievements?only_ready=true")
    assert "READY_SENTINEL" in chat["report"]
    assert "NEEDS_DATA_SENTINEL" not in chat["report"]
    assert "PENDING_SENTINEL" not in chat["report"]
    assert [item["cv"] for item in report.json()] == ["READY_SENTINEL"]

def test_copy_download_and_final_markdown_never_receive_non_ready_sentinel():
    markdown = generateReport(mixed_status_sentinels(), range, template).markdown
    assert "NEEDS_DATA_SENTINEL" not in markdown
    assert "PENDING_SENTINEL" not in markdown
```

Add cases for no ready achievements: chat states ready count zero and needs-attention count, rather than composing non-ready outcomes.

- [ ] **Step 2: Run the new tests to prove P0-2 is red.**

Run: `.venv312/bin/pytest app/tests/test_ready_only_output_boundaries.py -q`  
Expected: FAIL because `tool_generate_weekly_report` currently reads all weekly achievements.

- [ ] **Step 3: Implement the shared query and route every formal reader through it.**

`list_output_ready_achievements` must add `AchievementORM.cv_status == CVStatus.READY.value` itself, not rely on callers to remember a flag. Update chat weekly report to use `cv` only, return a ready-empty/needs-attention message when appropriate, and make current `/report` fetch ready entries for its rendered/copy/download markdown. Keep non-ready fetches confined to visible recovery cards.

- [ ] **Step 4: Lock all entry points, including MCP-compatible report paths.**

Audit `rg -n "list_achievements|generate.*report|download|clipboard" app web` and add each formal output caller to the test parameter set. Make `constitution` execute behavior rather than only assert source strings.

- [ ] **Step 5: Run output and constitution suites.**

Run: `.venv312/bin/pytest app/tests/test_ready_only_output_boundaries.py app/tests/test_report_workspace_invariants.py app/tests/constitution/test_output_and_write_boundaries.py -q`  
Expected: PASS; non-ready sentinels are absent from chat, markdown, copy/download source, and output lists.

### Task 5: P0-4 Remove CoT From Product Data Planes While Retaining Sanitization

**Files:**
- Create: `app/tests/test_cot_non_disclosure.py`
- Modify: `app/llm/chat_engine.py`
- Modify: `app/api/chat.py`
- Modify: `web/lib/hooks/useChatStream.ts`
- Modify: `web/components/ChatWindow.tsx`
- Modify: `app/tests/test_stream_chat.py`, `app/tests/test_markdown_fallback.py`, constitution tests

**Interfaces:**
- Produces: text/tool/error/start/end SSE contract with no `cot` event and no `cot_blocks` key. Think/reasoning stripping remains internal.

- [ ] **Step 1: Write red streaming, persistence, DOM, and tool-fallback tests.**

```python
async def test_stream_cross_chunk_think_is_never_emitted_or_persisted(client):
    events = await consume_stream(client, chunks=["<thi", "nk>secret tool call</think>可见文本"])
    assert all(event["event"] != "cot" for event in events)
    assert "cot_blocks" not in end_event(events)["data"]
    assert "secret tool call" not in await latest_persisted_assistant_message()
    assert visible_text(events) == "可见文本"

async def test_tool_shaped_text_inside_think_never_executes():
    result = await run_stream_with_reasoning("<think>{tool call}</think>正常回答")
    assert result.tool_calls == []

def test_chat_dom_has_no_cot_state_toggle_or_local_storage_key():
    assert_no_tokens(read("web/components/ChatWindow.tsx"), ["CotBlock", "cot", "思维链"])
```

- [ ] **Step 2: Run tests to confirm P0-4 red.**

Run: `.venv312/bin/pytest app/tests/test_cot_non_disclosure.py app/tests/test_stream_chat.py -q`  
Expected: FAIL because end SSE currently includes `cot_blocks`.

- [ ] **Step 3: Delete display/capture channels, retain parser defense.**

Delete `cot_blocks` accumulation, CoT SSE event, hook field, UI toggle/localStorage component and corresponding tests. Keep and centralize the sanitizer that strips paired and unpaired think/reasoning tags before markdown fallback, JSON parsing, tool-call parsing, output display, and persistence.

- [ ] **Step 4: Run focused non-disclosure and fallback tests.**

Run: `.venv312/bin/pytest app/tests/test_cot_non_disclosure.py app/tests/test_stream_chat.py app/tests/test_markdown_fallback.py -q`  
Expected: PASS; raw reasoning has no possible UI/SSE/persistence path.

### Task 6: Make Snapshot and Core Pages Truthful About Loading, Errors, and Status Counts

**Files:**
- Create: `app/tests/test_snapshot_readiness_counts.py`, `web/scripts/test-core-page-data-states.mjs`
- Modify: `app/core/models.py`, `app/core/storage.py`, `app/api/snapshot.py`
- Modify: `web/lib/api.ts`, `web/components/MainBoard.tsx`, `web/app/achievements/page.tsx`, `web/app/report/page.tsx`, `web/app/settings/page.tsx`

**Interfaces:**
- Produces: snapshot `counts` with `achievementsReady`, `achievementsNeedsData`, `achievementsPending`, and `achievementsNeedsAttention`; SWR consumers receive explicit loading/error states.

- [ ] **Step 1: Write failing count and source/runtime state tests.**

```python
async def test_snapshot_counts_each_readiness_state_and_attention_union(isolated_db):
    await seed_statuses(isolated_db, ready=1, needs_data=2, pending=3)
    counts = (await storage.build_snapshot()).counts
    assert counts == {"achievementsReady": 1, "achievementsNeedsData": 2,
                      "achievementsPending": 3, "achievementsNeedsAttention": 5}
```

The web test must assert `isLoading` renders a skeleton, fetch error renders retry plus settings/data-location action, and neither branch derives a visible number from `snapshot?.counts ?? 0`.

- [ ] **Step 2: Run red tests.**

Run: `.venv312/bin/pytest app/tests/test_snapshot_readiness_counts.py -q && node --experimental-strip-types web/scripts/test-core-page-data-states.mjs`  
Expected: FAIL because snapshot only exposes ready/pending and UI treats undefined as zero.

- [ ] **Step 3: Implement semantic counts and reusable data-state rendering.**

Compute all counts in storage from actual rows; pass them losslessly through API types. Add a small reusable `DataState` component or local equivalent that accepts loading/error/retry/settings action; distinguish successful empty data from unavailable backend/migration conflict/LLM unavailable.

- [ ] **Step 4: Run all Phase 1 focused tests and type-check.**

Run:

```bash
.venv312/bin/pytest \
  app/tests/test_data_directory_migration.py \
  app/tests/test_achievement_readiness_resolution.py \
  app/tests/test_complete_modal_suggestion_flow.py \
  app/tests/test_ready_only_output_boundaries.py \
  app/tests/test_cot_non_disclosure.py \
  app/tests/test_snapshot_readiness_counts.py -q
cd web && npx tsc --noEmit
```

Expected: PASS.

- [ ] **Step 5: Perform Phase 1 review and commit only Phase 1.**

Run `git diff --check`, inspect that no Phase 2 deletion is included, then:

```bash
git add app web .env.example README.md
git commit -m "fix: enforce achievement readiness and local data safety"
```

---

## Phase 2 — Product Subtraction

**Phase acceptance:** PR feature and task drafts are retired without losing data; CV becomes a redirect into output center; home navigation and onboarding are reduced; integrations are optional; normal project deletion is downgraded to a backed-up, strongly confirmed advanced flow. Phase 1 contracts remain untouched except consumers adopting user-facing labels.

### Task 7: Retire the PR Description Product Path Completely

**Files:**
- Delete: `web/app/pr/page.tsx`, `web/lib/pr.ts`, `web/scripts/test-*-pr*.mjs` only if no other consumer exists
- Modify: `app/api/llm.py`, `web/lib/api.ts`, `web/components/MainBoard.tsx`, `web/app/achievements/page.tsx`
- Modify/Delete: PR-only tests identified by `rg -n "generate_pr|PR_CANDIDATES_KEY|/pr" app web`

- [ ] **Step 1: Write a failing route/navigation/API absence test before removal.**

```python
def test_pr_route_and_api_are_not_registered(app):
    routes = {route.path for route in app.routes}
    assert "/pr" not in routes
    assert "/api/llm/generate_pr" not in routes

def test_main_navigation_has_no_pr_or_pr_candidate_storage():
    assert "/pr" not in read("web/components/MainBoard.tsx")
    assert "cockpit_pr_candidates" not in all_web_runtime_sources()
```

- [ ] **Step 2: Run red test, then remove only runtime PR dependencies.**

Run: `.venv312/bin/pytest app/tests/test_product_subtraction_routes.py::test_pr_route_and_api_are_not_registered -q`  
Expected: FAIL before deletion.

Delete API schema/prompt/fallback/handler, client method, page, candidate selection/localStorage and PR-only icons/tests. Do not alter historical changelog or lesson content; record its exit only in Phase 4 changelog.

- [ ] **Step 3: Verify no runtime PR references remain.**

Run: `rg -n "generate_pr|cockpit_pr_candidates|href=.*/pr|/api/llm/generate_pr" app web`  
Expected: no runtime matches; historical docs are allowed.

### Task 8: Remove `Task.draft` End-to-End With a Backup-First, Idempotent Schema Migration

**Files:**
- Create: `app/tests/test_task_draft_retirement.py`
- Modify: `app/core/models.py`, `app/core/storage.py`, `app/api/tasks.py`, `app/llm/tools.py`, `app/llm/prompts/cockpit_system.md`, `app/mcp_server.py`, `web/lib/api.ts`, `web/components/MainBoard.tsx`
- Modify: draft-specific test files and any API DTO assertions

- [ ] **Step 1: Write migration and endpoint/tool behavior tests.**

```python
async def test_draft_column_migration_keeps_rows_as_unfinished_tasks(tmp_sqlite):
    await create_legacy_tasks_table(tmp_sqlite, draft=True)
    backup = await run_schema_migrations(tmp_sqlite)
    assert backup.exists()
    assert await task_row(tmp_sqlite, "task_1") == {"status": "未开始", "title": "保留任务"}
    assert "draft" not in await sqlite_columns(tmp_sqlite, "tasks")

def test_task_api_tools_and_mcp_no_longer_expose_draft():
    assert "/confirm-drafts" not in task_router_paths()
    assert "confirm_drafts" not in tool_names()
    assert "draft" not in mcp_list_tasks_schema()
```

- [ ] **Step 2: Run red test, then introduce backup + migration before field deletion.**

Run: `.venv312/bin/pytest app/tests/test_task_draft_retirement.py -q`  
Expected: FAIL while draft schema/API exists.

Create a timestamped database backup, drop `tasks.draft` only after all historical `draft=true` rows remain otherwise unchanged, and make repeated startup a no-op. Remove Pydantic/ORM fields, task API and tool/prompt schema, UI toggle, MCP serialization and related tests/copy; never remove task rows.

- [ ] **Step 3: Verify migration and normal task flows.**

Run: `.venv312/bin/pytest app/tests/test_task_draft_retirement.py app/tests/test_storage.py app/tests/test_mcp_server.py -q`  
Expected: PASS, including repeated migration.

### Task 9: Merge CV Into `/report` and Preserve Only the Compatibility Redirect

**Files:**
- Delete: `web/app/cv/page.tsx`, `web/lib/cv-template.ts` after its pure logic is moved or replaced
- Modify: `web/app/report/page.tsx`, `web/lib/templates.ts`, `web/lib/api.ts`, navigation components
- Create: `web/app/cv/page.tsx` only as the smallest redirect route if framework requires a route file
- Create/Modify: `app/tests/test_output_center_routes.py`, `web/scripts/test-output-center.mjs`

- [ ] **Step 1: Write failing redirect and single-data-path tests.**

```python
def test_cv_route_redirects_to_output_center_with_all_range(browserless_route_client):
    assert browserless_route_client.get("/cv").location == "/report?type=cv&range=all"

def test_no_independent_cv_page_or_second_achievement_fetch():
    assert "generateCvMarkdown" not in read("web/app/cv/page.tsx")
    assert output_center_has_single_composer_entrypoint()
```

- [ ] **Step 2: Run red test, then move UI selection to output center.**

Add four output type controls in `/report` with `type=cv` and `range=all` query initialization; retain copy/download/edit. Remove independent CV business UI and data assembly. Keep the actual unified Composer implementation for Phase 3, but no page may retain an independent CV fetch/render path.

- [ ] **Step 3: Verify route and report UI invariants.**

Run: `.venv312/bin/pytest app/tests/test_output_center_routes.py app/tests/test_report_workspace_invariants.py -q && node --experimental-strip-types web/scripts/test-output-center.mjs`  
Expected: PASS.

### Task 10: Reduce Home, Navigation, Integrations, Duplicate Completion Views, Metrics, Tags, and Onboarding

**Files:**
- Modify: `web/components/MainBoard.tsx`, `web/components/OnboardingTooltip.tsx`, `web/components/FollowUpReminder.tsx`, `web/app/page.tsx`, `web/app/achievements/page.tsx`, `web/app/integrations/page.tsx`, `web/app/settings/page.tsx`
- Delete: `web/lib/commitments.ts`, `web/lib/achievement-stats.ts`, and their tests/scripts if no runtime consumers remain
- Modify: `web/lib/api.ts`, localStorage cleanup code
- Create: `app/tests/test_product_subtraction_ui_invariants.py`

- [ ] **Step 1: Write one failing behavior/invariant suite that describes the intended product surface.**

```python
def test_home_has_only_achievements_output_center_and_settings_as_top_level_destinations():
    links = top_level_navigation_targets(read("web/components/MainBoard.tsx"))
    assert links == {"/achievements", "/report", "/settings"}

def test_home_has_no_commitment_progress_done_task_foldout_or_project_seven_day_achievement_view():
    assert_no_tokens(read("web/components/MainBoard.tsx"), ["commitments", "done_tasks", "7 天内成就"])

def test_onboarding_is_inline_empty_state_not_delayed_modal():
    source = read("web/components/OnboardingTooltip.tsx")
    assert "setTimeout" not in source and "fixed inset-0" not in source

def test_integrations_are_reachable_from_settings_without_home_badge_polling_or_install_pressure():
    assert "/integrations" in read("web/app/settings/page.tsx")
    assert "refreshInterval: 30000" not in read("web/app/integrations/page.tsx")

def test_achievements_show_fact_health_and_reasons_not_verb_or_quantification_scores():
    assert_no_tokens(read("web/app/achievements/page.tsx"), ["量化率", "强动词", "动词分布", "优秀"])

def test_tags_absent_from_product_dto_and_ui_but_not_storage_export_contract():
    assert "tags:" not in read("web/lib/api.ts")
    assert "tags_json" in read("app/core/portability.py")
```

- [ ] **Step 2: Run red test and perform the subtraction.**

Run: `.venv312/bin/pytest app/tests/test_product_subtraction_ui_invariants.py -q`  
Expected: FAIL against the current expanded home UI.

Remove only Spec-listed product surfaces: commitment localStorage/UI, global completed-task foldout, project seven-day achievement repeat, PR/CV/integration home links, integration polling/red badge/install count, quantity/verb/distribution/grade UI, tags DTO/UI, onboarding overlay and re-show setting. Add inline empty-state steps and CTA to chat/new task. Place integrations under Settings → 高级接入 with optional-channel language. Remove stale localStorage keys defensively so their presence cannot crash UI.

- [ ] **Step 3: Update user-facing state labels without leaking internal names.**

Create one status label/reason mapping used by achievement, follow-up, modal, report and toast UI: `可直接使用`, `待补证据`, `草稿`. Remove `workspace`, CoT, model/path/session ids, `via LLM`, internal versions, and status enum literals from daily surfaces; retain diagnostics only in settings.

- [ ] **Step 4: Verify product subtraction UI and type-check.**

Run: `.venv312/bin/pytest app/tests/test_product_subtraction_ui_invariants.py app/tests/test_completion_toast_invariants.py -q && cd web && npx tsc --noEmit`  
Expected: PASS.

### Task 11: Downgrade Permanent Project Deletion to a Backed-Up Advanced Dangerous Operation

**Files:**
- Create: `app/tests/test_advanced_project_deletion.py`
- Modify: `app/core/storage.py`, `app/core/models.py`, `app/api/projects.py`, `app/llm/tools.py`, `app/llm/prompts/cockpit_system.md`
- Modify: `web/components/MainBoard.tsx`, `web/app/settings/page.tsx`, `web/lib/api.ts`
- Modify: `app/tests/constitution/test_irreversible_actions.py`, archive/delete invariants

- [ ] **Step 1: Write red tests for asset preservation and strong confirmation.**

```python
async def test_delete_preview_reports_tasks_achievements_and_requires_exact_name(client, seeded_project):
    preview = await client.get(f"/api/projects/{seeded_project.id}/danger-preview")
    assert preview.json()["achievement_count"] == 2
    denied = await client.post(f"/api/projects/{seeded_project.id}/danger-delete", json={"project_name": "wrong"})
    assert denied.status_code == 409

async def test_project_with_achievements_is_not_silently_destroyed_and_backup_exists(client, seeded_project):
    result = await client.post(f"/api/projects/{seeded_project.id}/danger-delete", json={"project_name": seeded_project.name})
    assert result.status_code in {409, 422}  # chosen policy: protect/move assets, never cascade them
    assert Path(result.json()["backup_path"]).exists()
```

- [ ] **Step 2: Run red test, decide schema-safe policy, and implement it.**

Run: `.venv312/bin/pytest app/tests/test_advanced_project_deletion.py app/tests/constitution/test_irreversible_actions.py -q`  
Expected: FAIL because normal deletion currently cascades tasks and does not account for achievements.

Before UI work, inspect foreign keys and explicitly implement the Spec-default asset policy: prohibit permanent deletion when achievements exist (with archive as default), or move achievements to a named `未归属/已删除项目` container without changing achievement ids/dates. Return preview impact counts, require exact name, create a recoverable backup/audit entry, retain chat’s list → explain → explicit-confirmation rule, and remove all common-board delete controls.

- [ ] **Step 3: Run destructive-operation regressions.**

Run: `.venv312/bin/pytest app/tests/test_advanced_project_deletion.py app/tests/test_archive_project_invariants.py app/tests/constitution/test_irreversible_actions.py -q`  
Expected: PASS.

### Task 12: Verify and Commit Phase 2 Independently

- [ ] **Step 1: Audit deleted consumer graph.**

Run:

```bash
rg -n "generate_pr|cockpit_pr_candidates|confirm_drafts|draft|achievement-stats|commitments" app web
rg -n "href=.*/pr|href=.*/cv|cot_blocks|CotBlock" web
```

Expected: only intentional historical comments/tests or compatibility redirect references; remove unintended runtime matches.

- [ ] **Step 2: Run Phase 2 regression suite and type-check.**

Run:

```bash
.venv312/bin/pytest \
  app/tests/test_product_subtraction_routes.py \
  app/tests/test_task_draft_retirement.py \
  app/tests/test_output_center_routes.py \
  app/tests/test_product_subtraction_ui_invariants.py \
  app/tests/test_advanced_project_deletion.py \
  app/tests/constitution/test_irreversible_actions.py -q
cd web && npx tsc --noEmit
```

- [ ] **Step 3: Commit only product-subtraction work.**

```bash
git add app web
git commit -m "feat: consolidate cockpit product surface"
```

---

## Phase 3 — Unified Output and Portability

**Phase acceptance:** `/report` is the one deterministic Composer-backed output center for weekly/monthly/review/CV, with ready-only achievements plus task/project context; data can be safely exported, previewed/imported/rolled back locally; feedback is local and trace-linked.

### Task 13: Build the Deterministic Shared Composer and Migrate `/report` to It

**Files:**
- Create: `app/core/composer.py`, `app/api/outputs.py`, `app/tests/test_composer.py`
- Modify: `app/main.py`, `app/core/storage.py`, `app/core/models.py`, `web/app/report/page.tsx`, `web/lib/api.ts`
- Delete/Reduce: `web/lib/templates.ts` and duplicate CV rendering once no caller remains

**Interfaces:**

```python
class OutputType(str, Enum):
    WEEKLY = "weekly"; MONTHLY = "monthly"; REVIEW = "review"; CV = "cv"

class ComposeOutputRequest(BaseModel):
    type: OutputType
    since: date | None = None
    until: date | None = None
    weekly_style: Literal["product", "engineering"] | None = None

class ComposeOutputResponse(BaseModel):
    markdown: str
    ready_achievement_count: int
    needs_attention_count: int
    used_achievement_ids: list[str]
```

- [ ] **Step 1: Write failing Composer tests before its implementation.**

```python
async def test_composer_uses_storage_ready_query_and_not_caller_filtered_list(monkeypatch):
    monkeypatch.setattr(storage, "list_output_ready_achievements", fake_ready_rows)
    result = await compose_output(ComposeOutputRequest(type=OutputType.WEEKLY, since=date(2026, 8, 3)))
    assert result.used_achievement_ids == ["ready_1"]
    assert "NEEDS_DATA_SENTINEL" not in result.markdown

async def test_composer_works_without_llm_and_includes_task_risk_and_next_plan_context(monkeypatch):
    monkeypatch.setattr(storage, "list_output_ready_achievements", fake_ready_rows)
    monkeypatch.setattr(storage, "list_tasks", fake_tasks_with_blocked_and_open_items)
    result = await compose_output(ComposeOutputRequest(type=OutputType.WEEKLY))
    assert "风险/阻塞" in result.markdown and "下周计划" in result.markdown
```

- [ ] **Step 2: Run red Composer tests.**

Run: `.venv312/bin/pytest app/tests/test_composer.py -q`  
Expected: FAIL because a Composer endpoint/core does not exist.

- [ ] **Step 3: Implement a pure deterministic Composer.**

Composer must call `list_output_ready_achievements` itself, fetch unfinished/blocked tasks and project descriptions only as contextual sections, and use no LLM/network. Return markdown plus IDs/counts so copy/download/edit operate on the exact audited output. Register `/api/outputs/compose`; update report UI to call it for every type/range, so it no longer composes a second independent template in the browser.

- [ ] **Step 4: Preserve Phase 1 chat compatibility while converging formatting.**

Refactor `tool_generate_weekly_report` to call `compose_output` using the same weekly input. The chat response may add conversational framing, but its markdown must be Composer output and must never rebuild bullets from raw achievements.

- [ ] **Step 5: Run Composer, chat, and ready-only suites.**

Run: `.venv312/bin/pytest app/tests/test_composer.py app/tests/test_ready_only_output_boundaries.py app/tests/constitution/test_output_and_write_boundaries.py -q`  
Expected: PASS.

### Task 14: Complete the Four Local Output Templates and Their Exact Time-Window Behavior

**Files:**
- Modify: `app/core/composer.py`, `app/tests/test_composer.py`, `web/app/report/page.tsx`, `web/scripts/test-output-center.mjs`

- [ ] **Step 1: Add failing parameterized template tests.**

```python
@pytest.mark.parametrize("kind,required_sections", [
    (OutputType.WEEKLY, ["已完成", "风险/阻塞", "下周计划"]),
    (OutputType.MONTHLY, ["关键成果", "项目进展", "问题", "下月重点"]),
    (OutputType.REVIEW, ["核心成果", "角色与行动", "证据", "复盘"]),
    (OutputType.CV, ["项目", "简历成就"]),
])
async def test_each_template_is_deterministic_ready_only_and_has_minimum_structure(kind, required_sections):
    result = await compose_output(ComposeOutputRequest(type=kind, since=date(2026, 8, 1), until=date(2026, 8, 31)))
    assert all(section in result.markdown for section in required_sections)
    assert "NEEDS_DATA_SENTINEL" not in result.markdown
```

Test this/last week, this/last month, quarter/year/custom review, and CV 1/2/3 years/all. Include exact date boundaries using local dates (not `new Date("YYYY-MM-DD")` parsing).

- [ ] **Step 2: Run red tests, implement sections, then test no-LLM behavior.**

Run: `.venv312/bin/pytest app/tests/test_composer.py -q && node --experimental-strip-types web/scripts/test-output-center.mjs`  
Expected: FAIL until all four shapes and selectors exist.

Use achievement `cv` for results; use task `blocked` for risks and incomplete tasks for planning. Template code must not invent outcome/ownership/numbers. Provide editable markdown, copy and download; no output depends on model availability.

- [ ] **Step 3: Verify all types are served through the one endpoint.**

Run: `rg -n "generateReport|generateCvMarkdown|listAchievements.*ready" web/app/report web/app/cv web/lib`  
Expected: no independent renderer/fetch remains outside the Composer API adapter.

### Task 15: Add Local Export, Previewed Import, Transaction Rollback, and Recovery Metadata

**Files:**
- Create: `app/core/portability.py`, `app/api/backup.py`, `app/tests/test_portability.py`
- Modify: `app/core/storage.py`, `app/main.py`, `web/app/settings/page.tsx`, `web/lib/api.ts`, `web/lib/types` if split

**Interfaces:**

```python
class ExportManifest(BaseModel):
    schema_version: int
    generated_at: datetime
    counts: dict[str, int]

async def export_cockpit_data() -> bytes:
    """Create a versioned local archive excluding secret settings."""
async def preview_cockpit_import(blob: bytes) -> ImportPreview:
    """Validate manifest/schema and calculate counts/conflicts without writing."""
async def import_cockpit_data(blob: bytes, *, confirmed: bool) -> ImportResult:
    """Backup first, then execute the confirmed import as one transaction."""
```

- [ ] **Step 1: Write failing round-trip, secrecy, preview, bad-package, conflict, and rollback tests.**

```python
async def test_export_round_trip_preserves_core_asset_tables_and_not_secret_settings(client):
    archive = await client.get("/api/backup/export")
    assert "sk-" not in archive.content.decode(errors="ignore")
    preview = await client.post("/api/backup/import/preview", files={"file": archive})
    assert preview.json()["counts"] == {"projects": 1, "tasks": 2, "achievements": 3, "messages": 4}

async def test_import_failure_rolls_back_and_retains_pre_import_backup(client, invalid_archive):
    before = await dump_core_tables()
    response = await client.post("/api/backup/import", files={"file": invalid_archive}, data={"confirmed": "true"})
    assert response.status_code == 422
    assert await dump_core_tables() == before
    assert await latest_pre_import_backup_exists()
```

- [ ] **Step 2: Run red portability tests.**

Run: `.venv312/bin/pytest app/tests/test_portability.py -q`  
Expected: FAIL because portability endpoints do not exist.

- [ ] **Step 3: Implement versioned self-only archive format.**

Export JSON or zip containing manifest and projects, tasks, achievements (including tags JSON), follow-up questions/answers, chat sessions/messages, traces and feedback. Never export API keys, encryption keys, environment variables, or unrelated settings. Validate format/schema before writes; preview row counts/conflicts and chosen strategy; only explicit confirmation imports.

- [ ] **Step 4: Make import recoverable and idempotently safe.**

Create pre-import database backup, execute data writes in one transaction, restore/retain backup upon failure, and report actionable error. First release accepts only Cockpit manifests, never silently merges unknown schema or overwrites collisions.

- [ ] **Step 5: Add Settings → 数据与备份 UI and run focused verification.**

Show export, local-file selection, preview counts/conflicts/strategy, explicit confirmation, backup result and retry/error states. Run: `.venv312/bin/pytest app/tests/test_portability.py -q && cd web && npx tsc --noEmit`  
Expected: PASS.

### Task 16: Make Local Adoption Feedback Complete and Non-Gamified

**Files:**
- Create: `app/tests/harness/test_completion_feedback_loop.py`
- Modify: `app/harness/feedback.py`, `app/core/storage.py`, `app/api/achievements.py`, `web/components/CompleteTaskModal.tsx`, `web/app/achievements/follow-up/page.tsx`

- [ ] **Step 1: Write failing trace-linkage tests.**

```python
async def test_first_completion_confirmation_records_candidate_to_final_feedback():
    achievement = await complete_with_candidate(trace_id="trace_1", candidate="修复登录问题", final="修复登录鉴权问题")
    feedback = await feedback_for_trace("trace_1")
    assert feedback.final_cv == achievement.cv
    assert feedback.adoption_label == "light_edit"
```

- [ ] **Step 2: Run red test, implement exactly-once local feedback persistence, then rerun it.**

Run: `.venv312/bin/pytest app/tests/harness/test_completion_feedback_loop.py app/tests/harness/test_feedback_persistence.py -q`  
Expected: initially FAIL, then PASS.

Do not add user-visible quality grades, growth statistics, remote upload, or new analytics. Surface only useful recovery reasons in the achievement list.

### Task 17: Verify and Commit Phase 3 Independently

- [ ] **Step 1: Run all Phase 3 behavioral tests and frontend checks.**

Run:

```bash
.venv312/bin/pytest \
  app/tests/test_composer.py \
  app/tests/test_ready_only_output_boundaries.py \
  app/tests/test_portability.py \
  app/tests/harness/test_completion_feedback_loop.py \
  app/tests/harness/test_feedback_persistence.py -q
cd web && npx tsc --noEmit
```

- [ ] **Step 2: Perform an offline smoke test.**

With no configured LLM, create/read a task, save a draft achievement, compose each output type, export, preview import, and verify no network call is required. Record command/result in commit notes or changelog only, not user data.

- [ ] **Step 3: Commit only Composer and portability work.**

```bash
git add app web
git commit -m "feat: unify local outputs and backup portability"
```

---

## Phase 4 — Documentation, Regression, and Dogfooding

**Phase acceptance:** implementation and product documentation are aligned, project gate passes, and two calendar weeks of genuine use produce 20 real achievements with adoption evidence. Synthetic harness output is kept distinct from real dogfooding; checklist/multi-session decisions are recorded only after the evidence period.

### Task 18: Align Prompt, Product Documents, Changelog, Lessons, and Harness Contracts

**Files:**
- Modify: `app/llm/prompts/cockpit_system.md`, `README.md`, `docs/PRD.md`, `docs/GOAL.md`, `AGENTS.md`, `docs/harness/capabilities-v1.yaml`, `docs/changelog/README.md`
- Create: `docs/changelog/2026-08-11-core-loop-consolidation.md`
- Modify: relevant `docs/lessons/*.md` indices only to add a new lesson/overturn chain; do not rewrite history

- [ ] **Step 1: Write a failing documentation/prompt consistency test.**

```python
def test_runtime_prompt_matches_readiness_and_output_contract():
    prompt = read("app/llm/prompts/cockpit_system.md")
    assert "只读取 ready 成就" in prompt
    assert "确认最终 CV" in prompt
    assert "confirm_drafts" not in prompt
    assert "PR 描述" not in prompt
    assert "思维链" not in prompt
```

Add a focused docs test/checklist asserting current routes/output types/test commands and resolved data directory wording; do not use broad brittle string-presence assertions for runtime behavior.

- [ ] **Step 2: Run red check and update documentation in factual order.**

Run: `.venv312/bin/pytest app/tests/test_documentation_alignment.py -q`  
Expected: FAIL until stale two-state/draft/PR/path/workspace language is removed.

Update prompt for the three statuses, explicit final CV confirmation, task retention, ready-only output, resolved setting path, no PR/drafts/forced quantification/CoT. Update README/PRD/GOAL/AGENTS to describe actual pages, data backup/import, tests and no longer-supported features. Add a changelog entry explaining PR exit/CV merge and link overturned records rather than editing old historical text. Update Harness capability requirements for new feedback/readiness/output tests.

- [ ] **Step 3: Verify docs and prompt alignment.**

Run: `.venv312/bin/pytest app/tests/test_documentation_alignment.py app/tests/harness/test_capabilities.py -q`  
Expected: PASS.

### Task 19: Replace Static Critical Invariants With Cross-Entry Behavior Regression Tests

**Files:**
- Modify: `app/tests/constitution/test_output_and_write_boundaries.py`, `app/tests/constitution/test_irreversible_actions.py`, `app/tests/test_complete_path_invariants.py`, `app/tests/test_stream_chat.py`, `app/tests/test_integrations.py`, `app/tests/test_mcp_server.py`, `app/tests/test_report_workspace_invariants.py`
- Create: `app/tests/test_core_loop_cross_entry.py`
- Modify: `app/scripts/run_project_gate.py`, `app/harness/project_gate.py` only if required to run behavioral groups

- [ ] **Step 1: Write the final cross-entry matrix test before relaxing any obsolete static test.**

```python
@pytest.mark.parametrize("entry", ["web_api", "chat_tool", "mcp"])
async def test_same_completion_evidence_has_same_persisted_readiness(entry, isolated_db):
    actual = await complete_via(entry, outcome="修复登录鉴权问题", cv="修复登录鉴权问题", claimed_status="ready")
    assert actual.cv_status is CVStatus.NEEDS_DATA
    assert "CV 尚未确认" in actual.unmet_reasons or "追问未答" in actual.unmet_reasons
```

Add separate tests for confirmed guardrail-clean completion → ready, all formal outputs → ready sentinel only, CoT non-disclosure, data migration conflict no writes, and UI completion response/toast/count coherence.

- [ ] **Step 2: Run red matrix against all routes, then correct tests/implementation without weakening guards.**

Run: `.venv312/bin/pytest app/tests/test_core_loop_cross_entry.py -q`  
Expected: fail until every entry actually calls the unified storage boundary.

- [ ] **Step 3: Wire behavioral suite into `make project-gate`.**

Project gate must execute this matrix and ready-only behavior suite, not merely inspect pages/source strings. Delete tests that only backed removed features; retain useful location-level UX static checks as supplements, not proof of P0 safety.

- [ ] **Step 4: Run the focused final behavior suites.**

Run: `.venv312/bin/pytest app/tests/test_core_loop_cross_entry.py app/tests/constitution/ -q`  
Expected: PASS.

### Task 20: Run the Full Regression Gate Before Beginning Real Dogfooding

- [ ] **Step 1: Ensure frontend dev server is not being used for a build.**

Run: `pgrep -f "next dev" || true`  
Expected: no `next build` is run regardless of result.

- [ ] **Step 2: Run the required final commands exactly.**

```bash
make clean
.venv312/bin/pytest app/tests/ -q
cd web && npx tsc --noEmit
cd .. && make project-gate
```

Expected: all commands pass. If a failure occurs, invoke systematic debugging, write/adjust the smallest behavioral regression first, and return to the failing phase; do not proceed to dogfooding with a red gate.

- [ ] **Step 3: Commit the Phase 4 code/doc/regression state before using it.**

```bash
git add app web docs README.md AGENTS.md .env.example
git commit -m "docs: align core loop contracts and regression gate"
```

### Task 21: Conduct Two Weeks of Genuine Dogfooding and Record the Exit Decision

**Files:**
- Create: `docs/harness/reports/2026-08-25-core-loop-dogfooding.md` (date moves to actual end date if execution starts later)
- Create only if evidence triggers it: `docs/rfcs/YYYY-MM-DD-checklist-or-session-retention.md`
- Modify: `docs/changelog/README.md` only to link the final real-use report if project convention calls for it

- [ ] **Step 1: Establish a local, non-synthetic evidence log before day 1.**

For every real achievement capture date/id, entry (Web/chat/MCP), candidate/final adoption label (`直接采用` / `轻改` / `重写` / `暂存` / `放弃`), whether follow-up was needed, output reuse, and any factual issue. Do not replace this with harness fixtures or fabricated rows.

- [ ] **Step 2: Use the core loop for 14 calendar days and at least 20 real achievements.**

Generate at least one real weekly report, monthly report, review and CV from ready achievements. For each output record direct-or-light-edit adoption; separately note LLM-unavailable/local-output behavior if encountered. Do not count synthetic data toward the target.

- [ ] **Step 3: Evaluate locked quality thresholds without moving them.**

Confirm: zero confirmed-fact fabrications; every output type has a real artifact; each type has at least 70% direct/light adoption; readiness feedback labels exist; no non-ready output leak. If a threshold fails, record the failure and open a narrowly scoped follow-up decision—do not declare the Spec complete or weaken a guardrail.

- [ ] **Step 4: Decide checklist and multi-session scope strictly from evidence.**

If 20 achievements use neither checklist nor session switching, write a deletion/simplification RFC preserving exports/history. If a real scenario used either, retain it and add/keep a usage-path test. Do not delete either feature in this plan merely because early local samples are sparse.

- [ ] **Step 5: Commit real-use evidence separately after the period closes.**

```bash
git add docs/harness/reports docs/rfcs docs/changelog
git commit -m "docs: record core loop dogfooding evidence"
```

---

## Spec Coverage Review

| Spec area | Plan tasks | Completion evidence |
|---|---|---|
| P0-1 follow-up cannot auto-ready; resolve + confirmation | 2, 3, 19 | transition and cross-entry tests |
| P0-2 ready-only all outputs | 4, 13, 14, 19 | sentinel tests and Composer-only path |
| P0-3 automatic suggestion preserves questions | 3 | auto/manual/race tests |
| P0-4 CoT removed | 5, 19 | SSE/persistence/DOM/tool tests |
| P0-5 expanded path + safe migration | 1, 19 | temp SQLite copy/conflict/idempotence tests |
| loading/error and real counts | 6 | snapshot and page-state tests |
| PR/CV/integrations/metrics/onboarding/navigation reduction | 7, 9, 10 | route/UI consumer audits |
| task draft migration; tags compatibility | 8, 10, 15 | migration and round-trip tests |
| advanced deletion protection | 11 | preview/name/backup/asset tests |
| four deterministic outputs + offline support | 13, 14, 17 | Composer tests and offline smoke |
| export/import preview/rollback | 15 | round-trip/secrecy/rollback tests |
| feedback and Harness distinction | 2, 16, 18, 21 | trace tests and real-use report |
| prompt/docs/changelog/lessons | 18 | docs alignment test and exit record |
| complete regression/project gate | 19, 20 | required command output |
| two-week real dogfooding and evidence-based retention | 21 | dated report / optional RFC |

## Plan Self-Review

- **Order:** Every implementation task is nested in the Spec-required Phase 1 → 4 order. UI/product subtraction starts only after the full Phase 1 safety commit.
- **P0 test-first:** Tasks 1–5 each explicitly write and execute a failing P0 behavior test before implementation.
- **Cross-entry consistency:** Readiness is storage-owned (Task 2); Web auto/manual flow (Task 3), chat/MCP (Tasks 4, 13, 19) share it.
- **No hidden data destruction:** Database migration, draft column removal, import, and advanced project deletion each require backup/transaction/protection tests; tags and historical records are retained.
- **No scope expansion:** Refiner/Git/KG/team/cloud/mobile are absent. Checklist and multi-session only receive a post-dogfood decision record.
- **Verification:** Each phase specifies focused proof and an independent commit; Phase 4 additionally requires the full test, type, and project-gate commands and a real 14-day evidence period.

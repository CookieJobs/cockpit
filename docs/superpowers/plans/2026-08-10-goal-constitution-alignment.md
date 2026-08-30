# Goal 与项目宪法对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Cockpit goal document and project instructions with the AI constitution and the implemented three-state achievement readiness model.

**Architecture:** This is a documentation-only alignment. `docs/GOAL.md` becomes the product and milestone source of truth, while `AGENTS.md` records the implementation-facing `cv_status` contract. No runtime behavior, schema, or API changes occur.

**Tech Stack:** Markdown, Git, ripgrep.

## Global Constraints

- Preserve Cockpit as a local-first product for individuals, not teams or autonomous agents.
- Automated collection must be user-authorized, source-traceable, and require confirmation before persisting a career asset.
- Preserve the implemented `cv_status` values: `ready`, `needs_data`, and `pending`.
- Do not modify application code, schemas, MCP tools, or frontend behavior.

---

### Task 1: Align product positioning and roadmap acceptance criteria

**Files:**
- Modify: `docs/GOAL.md:1-133`
- Test: `docs/GOAL.md` text-contract search

**Interfaces:**
- Consumes: `.ai/AI_CTO.md` principles for individual users, local-first operation, human control, and non-DAU north-star metrics.
- Produces: A roadmap that defines authorization, evidence, confirmation, target user, and measurable validation thresholds.

- [ ] **Step 1: Specify the failing text contract**

Run:

```bash
rg -n '用户授权|来源证据|用户确认|团队版|核心指标.*DAU|首要用户画像|可采用率' docs/GOAL.md
```

Expected: the required safeguards and measurable terms are absent; deprecated terms remain.

- [ ] **Step 2: Update the goal document**

Replace autonomous and dependency-led claims with user-authorized candidate collection; replace team/DAU metrics with individual outcome metrics; define the seed user and acceptance criteria; define mem9 as optional and replaceable; and keep MCP as an authorized intake channel.

- [ ] **Step 3: Verify the updated text contract**

Run:

```bash
rg -n '用户授权|来源证据|用户确认|首要用户画像|可采用率|事实编造率|候选确认率' docs/GOAL.md
! rg -n '团队版|核心指标（DAU' docs/GOAL.md
```

Expected: all required safeguards are present and the prohibited product/metric terms are absent.

- [ ] **Step 4: Commit**

```bash
git add docs/GOAL.md
git commit -m "docs: align goal with product constitution"
```

### Task 2: Correct the implementation-facing status contract

**Files:**
- Modify: `AGENTS.md:142`
- Test: `AGENTS.md` and `app/core/models.py` text-contract search

**Interfaces:**
- Consumes: `CVStatus` enum values in `app/core/models.py` and centralized readiness enforcement in `app/core/storage.py`.
- Produces: Agent instructions that name the same readiness states as runtime code and prevent callers from bypassing the quality gate.

- [ ] **Step 1: Specify the failing text contract**

Run:

```bash
rg -n 'cv_status.*ready / pending' AGENTS.md
rg -n 'class CVStatus|NEEDS_DATA|PENDING' app/core/models.py
```

Expected: `AGENTS.md` describes two states while the implementation contains three.

- [ ] **Step 2: Update the status contract**

Document `ready / needs_data / pending`, define their user-facing readiness meaning, and state that `storage.complete_task` decides persisted readiness from evidence rather than accepting an entry-point override.

- [ ] **Step 3: Verify contract consistency and Markdown validity**

Run:

```bash
rg -n 'ready / needs_data / pending|统一写入边界|不能.*绕过' AGENTS.md
rg -n 'class CVStatus|READY|NEEDS_DATA|PENDING' app/core/models.py
git diff --check -- docs/GOAL.md AGENTS.md
```

Expected: all three states and the shared-write-boundary rule are documented; Git reports no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs: align achievement status contract"
```

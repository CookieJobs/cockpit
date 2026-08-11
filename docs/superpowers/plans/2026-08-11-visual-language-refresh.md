# Visual Language Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Cockpit read as a calm, professional personal-achievement product rather than a generic dark admin console.

**Architecture:** Preserve the existing CSS-variable theme system. Redefine token semantics so indigo means interaction, gold means reusable career assets, and warning retains an independent orange. Apply those tokens first to the global shell and output surfaces, then reduce nested borders in the achievement library and compact empty report states.

**Tech Stack:** Next.js 15, React, Tailwind 3, CSS variables, Node ESM regression scripts.

## Global Constraints

- Keep light/dark switching via CSS variables and `darkMode: "class"`.
- Do not add external UI, icon, or font dependencies.
- Preserve all task/achievement data behaviour and all ready/needs-data/pending semantics.
- Do not run `next build` while a development server may be running.
- Verify 390×844 and 1280px in the browser after implementation.

---

### Task 1: Establish semantic colour tokens

**Files:**
- Modify: `web/app/globals.css`
- Modify: `web/tailwind.config.ts`
- Create: `web/lib/visual-system.ts`
- Test: `web/scripts/test-visual-tokens.mjs`

**Interfaces:**
- Produces Tailwind colours `accent` (interaction), `asset` (achievement value), `warning` (risk/data gap), plus the component-consumable `getVisualTone()` role mapping.

- [ ] Write a failing token contract that calls the not-yet-created role mapping and expects all three distinct semantic visual treatments.
- [ ] Run `node --experimental-strip-types scripts/test-visual-tokens.mjs`; verify it fails because the mapping does not yet exist.
- [ ] Add `asset` to the CSS-variable and Tailwind token layers; make accent indigo, asset gold, warning orange, and refine dark surfaces to blue-grey. Implement the mapping from user-visible role to Tailwind treatment so components share the semantic boundary.
- [ ] Re-run the token contract and `npx tsc --noEmit`.

### Task 2: Make value and interaction visually distinct in the main and achievement surfaces

**Files:**
- Modify: `web/components/MainBoard.tsx`
- Modify: `web/app/achievements/page.tsx`
- Test: `web/scripts/test-visual-tokens.mjs`

**Interfaces:**
- Consumes `asset` for value accumulation and `accent` for selected controls / interactive focus.

- [ ] Extend the failing contract to require a distinct asset visual class and a dense achievement item presentation.
- [ ] Run the contract and verify the expected failure.
- [ ] Move the main achievement spotlight and achievement-library value indicators to asset; keep filters and editing focus on accent.
- [ ] Replace achievement-item card repetition with divider-based rows inside each project group; retain explicit cards for projects and quality summary only.
- [ ] Re-run the contract, existing achievement tests, and type checking.

### Task 3: Improve report density, typography and empty states

**Files:**
- Modify: `web/app/report/page.tsx`
- Modify: `web/app/globals.css`
- Test: `web/scripts/test-visual-tokens.mjs`

**Interfaces:**
- Consumes the semantic tokens and presents empty report recovery as one compact summary.

- [ ] Extend the failing contract for the report's `asset` / `warning` separation and body text scale.
- [ ] Run it and verify the expected failure.
- [ ] Make report choices use interaction colour; make data-completeness cards compact, use asset only for the report value count, and raise reading text to 13–14px where it is content rather than metadata.
- [ ] Re-run all frontend regression scripts, inspect no whitespace errors, and validate light/dark browser screenshots at mobile and desktop widths.

### Task 4: Record the visual decision

**Files:**
- Create: `docs/changelog/2026-08-11-visual-language-refresh.md`
- Modify: `docs/changelog/README.md`
- Modify: `docs/lessons/05-theme-system.md`

- [ ] Record the semantic colour system, the nested-card decision, screenshots/viewport validation, and the reason not to introduce gradients or a third-party design system.
- [ ] Review the document for placeholders and ambiguous token ownership.

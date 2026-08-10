# Achievement Readiness Gate Design

## Goal

Keep task completion fast while ensuring that only complete, evidence-grounded achievements can feed reports, PR descriptions, and future CV output.

## Problem

The completion modal defaults to `ready` even when its CV field is still the title-based fallback or the AI returned unanswered follow-up questions. The report workspace consumes `ready` achievements, while the follow-up queue excludes them. Consequently, incomplete data is both output and hidden from its recovery path.

## Decision

Introduce a deterministic readiness gate at the shared storage boundary. The caller may request a status, but storage derives the persisted status from completion evidence:

- Persist `needs_data` when a caller requests `ready` but there are unanswered follow-up questions, the CV equals the title fallback `完成「<title>」`, or the trimmed outcome is shorter than 10 characters.
- Preserve an explicit user choice of `pending`; otherwise persist the derived status. This permits `ready` only for complete data.
- A completed task is always stored; the gate never blocks task completion.
- `answer_follow_ups` promotes an achievement to `ready` only after every stored follow-up has a non-empty answer. Partial answers remain `needs_data`.

The gate is deterministic program logic, not an LLM judgement. It applies to web, chat-tool, and MCP callers because they share `storage.complete_task`.

## UX and Data Flow

1. User completes a task with outcome, CV, and optional AI follow-ups.
2. Storage writes the achievement and derives `needs_data` if critical evidence is incomplete.
3. `ready`-only output views exclude that achievement.
4. The follow-up queue exposes incomplete achievements with questions.
5. After all answers are saved, the achievement becomes `ready` and joins the output pool.

No external service, product-positioning change, destructive operation, schema migration, or automatic external notification is introduced.

## Verification

- Storage/API tests prove fallback CV, short outcome, and unanswered follow-ups cannot persist as `ready`.
- Tests prove partial follow-up answers do not promote readiness and complete answers do.
- Existing report-ready filtering tests remain green.
- Frontend type checking and the backend suite validate integration.

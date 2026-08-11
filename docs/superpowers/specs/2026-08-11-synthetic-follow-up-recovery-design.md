# Synthetic Follow-up Recovery — Design

## Purpose

Extend Synthetic Dogfooding Harness v1 to verify Cockpit's recoverable evidence
path: an initially incomplete achievement must remain `needs_data`, receive
explicit follow-up evidence, have its CV statement revised against that evidence,
then become `ready` and appear in output exactly once.

## Data contract

`WorkEvent` gains optional recovery fields: follow-up answers and `recovered_cv`.
They are valid only together and only when the expected initial readiness is
`needs_data`. Numeric claims in `recovered_cv` must occur in outcome, evidence,
or follow-up answers. The original CV remains the initial incomplete statement.

## Replay boundary

For a recovery event, the runner uses only public HTTP APIs in this sequence:

1. `POST /api/tasks/{id}/complete` with `needs_data` and follow-up questions.
2. `PATCH /api/achievements/{id}/follow_ups` with answers.
3. `PATCH /api/achievements/{id}` with the evidence-grounded `recovered_cv`.

The runner asserts the initial response is `needs_data`, and the final response is
`ready`. It does not alter storage internals or database rows directly.

## Review and acceptance

The reviewer calculates recovery as recovered initial `needs_data` events divided
by all initial `needs_data` events. A recovered CV must be present in a report only
after ready status and must retain a source event mapping. The fixture includes one
completed recovery and three intentionally outstanding items, giving an expected
baseline recovery rate of 25%.

P0 remains any non-ready or unknown achievement in output. A recovery API failure,
missing revised CV, or incorrect recovery rate is P1.

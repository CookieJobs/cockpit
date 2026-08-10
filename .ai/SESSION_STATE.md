# Cockpit AI Session State

> Last updated: 2026-08-10

## Current loop

- **Capability:** Achievement Distillation (`polish_cv`)
- **Completed decision:** adopt the facts-grounded prompt experiment as `polish_cv_facts_grounded_v1`.
- **Safety invariant:** runtime P0 provenance guardrail remains unchanged; never weaken it to improve a score.

## Evidence

- Fixed-output calibrated baseline: Current Capability `13/19` (68.4%), fallback `16.7%`, hard-safety violations `0%`.
- Production L1 re-run after the prompt change: `16/19` (84.2%), fallback `5.3%`, hard-safety violations `0%`.
- Production semantic re-run: `13/19` (68.4%) under the minimal judge. This judge uses the configured client and is a quality signal, not independent human ground truth.

## Current top failure modes

1. Sparse or participation-only inputs still collapse to the generic fallback CV instead of yielding useful, fact-seeking follow-ups.
2. Some outputs repeat the supplied outcome rather than distilling it into a distinct resume statement.
3. The model can still emit unsupported target/result wording in edge cases; the guardrail prevents unsafe delivery, but causes fallback.

## Next approved work

- Do **not** tune this prompt again without a new harness hypothesis and comparative run.
- Prioritize structured fact extraction / controlled generation only after reviewing the semantic failures above.
- Extend L2 with independent judging or human sampling before treating semantic scores as release gates.

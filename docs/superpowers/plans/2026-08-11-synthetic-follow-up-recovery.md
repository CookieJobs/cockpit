# Synthetic Follow-up Recovery — Implementation Plan

1. Add a failing fixture-contract test for paired recovery answers and revised CV;
   implement the constrained fields in `app/harness/synthetic/models.py` and one
   recoverable fixture event.
2. Add a failing runner test that observes initial `needs_data` and final `ready`;
   replay recovery through the existing public follow-up and achievement PATCH APIs.
3. Add a failing reviewer assertion for 25% recovery, validate ready-only report
   output contains the revised fact-grounded CV, then update the baseline document.
4. Run focused harness tests, full backend tests, TypeScript checking, and
   `make project-gate`; commit each coherent stage on `main`.

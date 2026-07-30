# Are parallel-experiment / race-condition claims accurate?

**Status:** Closed as audit findings confirmed in **1.0.3+**. Serial Judge scheduling documented in README; per-case file lock + atomic `append_many` landed. Spec §10 parallel orchestration remains **not implemented** (intentional gap, not a regression).

## Symptoms (historical)
A prior assistant answer claimed:
1. Analyst may batch-propose many hypotheses/experiments into Case State.
2. Judge schedules only one next action at a time (one runnable or one proposed).
3. Execution is sequential handoffs, not a parallel worker pool.
4. No real concurrency control: JSONL append without lock/CAS; project-then-append TOCTOU; mid-batch partial writes; concurrent verify unsafe.
5. Race avoidance relies on single-agent policy, not infrastructure.
6. Spec allows concurrent experiments under rules, but that orchestration is not implemented.
7. Practical guidance: propose many, approve/verify one-by-one; do not parallel submit/verify on same case_id.

## Success criteria
- Each claim confirmed or falsified with code/spec evidence and/or runnable checks.
- If gaps are real and in-scope to fix for safety, implement minimal concurrency/atomicity guards (or document intentional serial policy) and verify.
- Suite green.

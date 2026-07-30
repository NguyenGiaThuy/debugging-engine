# Verifier visibility and missing autonomous fix loop

**Status:** Fixed in **1.0.3+** (Implementer/Verifier scheduling, intervention-before-accept, skill handoff rules). Covered by `tests/test_scheduling_autonomy.py` and investigate skill loop.

## Symptoms (historical)
1. During investigations, the Verifier role does not appear as a distinct step in chat, so it is unclear whether verification is scheduled or evidence is being collected correctly.
2. Investigations stop at reporting / escalation instead of implementing and verifying fixes. Spec and demo intend intervention experiments with patches; the live skill/Judge path escalates too early. User expects full autonomy through fix, escalating only for groundbreaking/safety/human-only cases.

## Observed clues
- `schedule_next_task` can return `role=Verifier` for APPROVED/SCHEDULED/RUNNING experiments, but agents often call `verify` immediately after Judge approve without a `next` handoff.
- `_slice_for_role` defines Implementer, yet `schedule_next_task` never returns `AgentRole.IMPLEMENTER`.
- Patches are applied inside `run_verification` with producer Implementer, collapsing Implementer into Verifier.
- After `InterpretationSubmitted(SUPPORTS)`, hypothesis status remains `PROPOSED`, so Judge never enters the "Evidence may be sufficient" branch (requires SUPPORTED/PLAUSIBLE/STRONGLY_SUPPORTED) and falls through to stall/escalate.
- Skill stop condition is RootCauseAccepted | Escalated; it does not require proposing/verifying an intervention fix first.

## Success criteria
- Documented + tested behavior: Verifier handoff is reachable via `next` after approve; skill instructs agents to announce role and run `next` before `verify`.
- Judge schedules Implementer (or an explicit patch-materialize step) for approved intervention experiments with patches, OR skill+scheduler clearly own patch application without a dead Implementer role.
- After supporting evidence, workflow prefers promoting hypotheses and proposing intervention fix experiments; escalate only for groundbreaking/safety/human-only stalls.
- Regression tests cover Verifier scheduling, Implementer scheduling (or intentional collapse), and post-interpretation promotion/fix path.
- Suite green; prior path-escape issues remain tracked separately.

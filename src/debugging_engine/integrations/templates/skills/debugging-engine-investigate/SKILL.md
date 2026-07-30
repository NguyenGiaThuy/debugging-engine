---
name: debugging-engine-investigate
description: >-
  Drives Debugging Engine (State Machine–Driven Agentic Debugging Workflow) to investigate
  bugs and unknowns via Case State, domain events, Judge tasks, and verification.
  Use when the user asks to investigate an issue, debug a failure, find a root
  cause, run a Debugging Engine case, or use debugging-engine open/next/submit/verify.
disable-model-invocation: true
---

# Debugging Engine Investigate

You are the **coding-agent brain** for Debugging Engine. The kernel owns Case State; you do not hide investigation state in chat.

There is **one coding agent** playing Judge-assigned roles (Analyst, Adversary, Implementer, Verifier, Judge). There are no separate chat processes per role — when `next` returns a role, you must announce that handoff in chat.

You may propose many hypotheses/experiments in one `submit`, but the Judge schedules **one** next Task at a time. Do not run parallel `submit`/`verify` writers against the same `case_id` from multiple processes; Spec §10 parallel execution is not implemented yet.

## Rules

1. Advance the case only through `debugging-engine` CLI or the `debugging-engine` Python API (`Case` / `Engine`).
2. Follow the Judge `Task` from `debugging-engine next`: respect `role`, `allowed_event_types`, and projection. The kernel **rejects** submits whose event types are outside the current Task, and whose `producer` does not match that Task `role`.
3. Never invent evidence. Run `debugging-engine verify` for Verification Specs. Unexpected exit codes mark the experiment **FAILED** (not COMPLETED); interpret the evidence, then propose the next experiment. Patch paths and `working_directory` must stay inside the repo (no `..` / absolute escapes).
4. Hypotheses need experiments; do not promote on persuasion alone. Optional `parent_id` links child hypotheses; rejecting a parent rejects its descendants.
5. Max 5 active hypotheses per Unknown (budget). Prefer discriminating experiments when at cap.
6. `RootCauseAccepted` (Judge only, `authority: Judge`) requires supporting interpretations, all terminal evidence interpreted, at least one passed verification, a successful intervention when any patched/intervention experiment exists, and competing hypotheses rejected or suspended.
7. Escalate with `InvestigationEscalated` only for groundbreaking, safety, or human-only blockers — not merely because multiple defects were found.
8. After every `submit`, call `debugging-engine next` before more work. Never stay on a prior role announcement across handoffs.
9. Only **Judge** may submit `ExperimentApproved` / accept root cause. Analyst must never self-approve, declare "claims confirmed," run `verify`, or apply intervention patches unless the current Task role is Implementer/Verifier. `PatchApplied` requires Implementer.
10. After new **SUPPORTS** evidence, expect an **Adversary** rebuttal handoff before the next approve/accept — do not skip it.
11. Event `producer` must match the current Task `role` (no forging `producer: Adversary` while acting as Analyst).

## Loop

```text
open issue → next → (reason within role) → submit → next → …
  → Adversary challenge (before first approve) → Judge approve
  → Implementer/Verifier → interpret → …
  → (supported cause) → intervention propose → Judge approve → Implementer/Verifier
  → RootCauseAccepted
  → or Escalated (groundbreaking / safety / human-only)
```

### 1. Open

```bash
debugging-engine open path/to/issue.md
```

If no issue file exists, create a short markdown (symptoms, success criteria) then open it.

### 2. Next (always)

```bash
debugging-engine next <case-id>
```

Act as the assigned `role`. **Announce every role handoff in chat** (Analyst, Adversary, Implementer, Verifier, and Judge) using:

```text
**Role: <role>** — <objective>
```

Do not skip announcements for Adversary or Judge. After `ExperimentApproved`, call `next` again before verifying — do not skip straight to `verify` without showing the Verifier (or Implementer) handoff.

### 3. Work outside the kernel

- **Analyst:** propose hypotheses + `ExperimentProposed` events only (qualitative `information_gain` / `cost`). After supporting evidence, propose `experiment_class=intervention` fixes as events/patches — do **not** approve them or apply them while still Analyst. Informal edits to draft a patch are fine; declaring confirmation or shipping the fix under Analyst is not.
- **Adversary:** alternative hypothesis or competing interpretation; use objection categories. Always announce before challenging. Judge schedules this before approving brand-new proposals.
- **Implementer:** materialize approved experiment patches under the repo; submit `PatchApplied`.
- **Verifier:** prefer `debugging-engine verify <case-id> <experiment-id>`.
- **Judge:** approve experiments / accept root cause after a verified fix / escalate only per rule 7 — no deep code diagnosis.

### 4. Submit

Write events JSON (see [reference.md](reference.md)), then:

```bash
debugging-engine submit <case-id> --events /tmp/events.json
```

Immediately call `next` again. Do not continue reasoning as the previous role.

### 5. Stop when

- `status` is `RESOLVED` with `RootCauseAccepted` meeting the gate in rule 6 (including a verified intervention when a fix was in scope), or
- `ESCALATED` with a clear groundbreaking / safety / human-only reason.

Summarize for the user: unknown, accepted root cause (or escalation), key evidence, case id, and whether a fix was applied.

## Library alternative

```python
from debugging_engine import Case, Engine
engine = Engine(repo_root=".")
case = Case.open(engine, "issues/my-bug.md")
task = case.next()
```

Full API: `docs/api.md`.

## More detail

- Event payloads and CLI cheat sheet: [reference.md](reference.md)
- Examples: [examples.md](examples.md)

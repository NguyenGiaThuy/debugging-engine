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

There is **one coding agent** playing Judge-assigned roles (Analyst, Adversary, Implementer, Verifier, Judge). There is no separate Verifier chat process — when `next` returns `role=Verifier`, announce that handoff and run verify.

## Rules

1. Advance the case only through `debugging-engine` CLI or the `debugging-engine` Python API (`Case` / `Engine`).
2. Follow the Judge `Task` from `debugging-engine next`: respect `role`, `allowed_event_types`, and projection.
3. Never invent evidence. Run `debugging-engine verify` for Verification Specs.
4. Hypotheses need experiments; do not promote on persuasion alone.
5. Max 5 active hypotheses per Unknown (budget). Prefer discriminating experiments when at cap.
6. Drive through a verified **intervention fix** before `RootCauseAccepted` when a code fix is in scope.
7. Escalate with `InvestigationEscalated` only for groundbreaking, safety, or human-only blockers — not merely because multiple defects were found.

## Loop

```text
open issue → next → (reason/edit) → submit and/or verify → next → …
  → (supported cause) → intervention fix → verify → RootCauseAccepted
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

Act as the assigned `role`. **Announce the role and objective in chat** so handoffs (especially Verifier / Implementer) are visible.

After `ExperimentApproved`, call `next` again before verifying — do not skip straight to `verify` without showing the Verifier (or Implementer) handoff.

### 3. Work outside the kernel

- **Analyst:** hypotheses + experiment proposals (qualitative `information_gain` / `cost`). After supporting evidence, propose `experiment_class=intervention` fixes.
- **Adversary:** alternative hypothesis or competing interpretation; use objection categories.
- **Implementer:** materialize approved experiment patches under the repo; submit `PatchApplied`.
- **Verifier:** prefer `debugging-engine verify <case-id> <experiment-id>`.
- **Judge:** approve experiments / accept root cause after a verified fix / escalate only per rule 7 — no deep code diagnosis.

### 4. Submit

Write events JSON (see [reference.md](reference.md)), then:

```bash
debugging-engine submit <case-id> --events /tmp/events.json
```

### 5. Stop when

- `status` is `RESOLVED` with `RootCauseAccepted` **after** a successful intervention verification when a fix was required, or
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

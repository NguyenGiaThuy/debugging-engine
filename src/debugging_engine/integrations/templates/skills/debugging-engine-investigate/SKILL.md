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

## Rules

1. Advance the case only through `debugging-engine` CLI or the `debugging-engine` Python API (`Case` / `Engine`).
2. Follow the Judge `Task` from `debugging-engine next`: respect `role`, `allowed_event_types`, and projection.
3. Never invent evidence. Run `debugging-engine verify` for Verification Specs.
4. Hypotheses need experiments; do not promote on persuasion alone.
5. Max 5 active hypotheses per Unknown (budget). Prefer discriminating experiments when at cap.
6. Escalate with `InvestigationEscalated` when stalled or human-only knowledge is required.

## Loop

```text
open issue → next → (reason/edit) → submit events and/or verify → next → … → RootCauseAccepted | Escalated
```

### 1. Open

```bash
debugging-engine open path/to/issue.md
```

If no issue file exists, create a short markdown under `subject/issues/` (symptoms, success criteria) then open it.

### 2. Next

```bash
debugging-engine next <case-id>
```

Act as the assigned `role` (Analyst, Adversary, Implementer, Verifier, Judge).

### 3. Work outside the kernel

- **Analyst:** hypotheses + experiment proposals (qualitative `information_gain` / `cost`).
- **Adversary:** alternative hypothesis or competing interpretation; use objection categories.
- **Implementer:** patches under the subject tree only as approved experiments require.
- **Verifier:** prefer `debugging-engine verify <case-id> <experiment-id>`.
- **Judge:** approve experiments / accept root cause / escalate — no deep code diagnosis.

### 4. Submit

Write events JSON (see [reference.md](reference.md)), then:

```bash
debugging-engine submit <case-id> --events /tmp/events.json
```

### 5. Stop when

- `status` is `RESOLVED` with `RootCauseAccepted`, or
- `ESCALATED` with a clear reason.

Summarize for the user: unknown, accepted root cause (or escalation), key evidence, case id.

## Library alternative

```python
from debugging_engine import Case, Engine
engine = Engine(repo_root=".")
case = Case.open(engine, "subject/issues/001-cache-miss.md")
task = case.next()
```

Full API: `docs/api.md`.

## More detail

- Event payloads and CLI cheat sheet: [reference.md](reference.md)
- Examples: [examples.md](examples.md)

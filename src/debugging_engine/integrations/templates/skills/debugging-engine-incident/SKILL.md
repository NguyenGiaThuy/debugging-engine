---
name: debugging-engine-incident
description: >-
  Fixes bugs and production incidents with Debugging Engine: investigate if needed,
  then Implementer patches, verify, and RootCauseAccepted. Use for SEV/outages,
  production failures, or when the user asks to fix an issue already reported under
  issues/. For report-only root-cause work use debugging-engine-investigate.
disable-model-invocation: true
---

# Debugging Engine Incident

You are the **coding-agent brain** for Debugging Engine in **fix** mode. Same kernel as [debugging-engine-investigate](../debugging-engine-investigate/SKILL.md), but you **may** propose interventions, act as Implementer, and verify fixes.

Prefer starting from an existing `issues/<slug>.md` brief (from investigate). If missing, write one first (impact, start time, deploys, blast radius, success criteria), then `open` it.

## Rules (in addition to investigate kernel rules)

1. Follow Judge Tasks, including **Implementer** when scheduled.
2. Prefer **observational** experiments first; then propose `experiment_class=intervention` with a contained `patch` when evidence supports a fix.
3. Mark production/risky interventions `cost: HIGH` or `CRITICAL`; escalate if policy or access blocks them.
4. `RootCauseAccepted` after a successful intervention when any patched/intervention experiment exists (Judge only, `authority: Judge`).
5. Competing hypotheses must be rejected or suspended before accept.
6. After new SUPPORTS evidence, expect Adversary rebuttal before approve/accept.
7. Event `producer` must match Task `role`. Never forge Adversary/Implementer producers.

## Loop

```text
open issues/<slug>.md → next → …
  → Adversary → Judge approve → Verifier (observe) → interpret → …
  → Analyst proposes intervention → Adversary (if needed) → Judge approve
  → Implementer (PatchApplied) → Verifier → interpret → …
  → RootCauseAccepted
  → or Escalated (groundbreaking / safety / human-only / blocked access)
```

### Role work

- **Analyst:** hypotheses + experiments; after supporting evidence, propose intervention patches (do not self-approve or apply them as Analyst).
- **Adversary:** competing hypotheses/interpretations; announce every handoff.
- **Implementer:** materialize approved patches; submit `PatchApplied`.
- **Verifier:** `debugging-engine verify <case-id> <experiment-id>`.
- **Judge:** approve / accept / escalate.

Announce every role handoff:

```text
**Role: <role>** — <objective>
```

## Production extras

1. Capture SEV symptoms: impact, start time, recent deploys, dashboards, blast radius.
2. Competing hypotheses should include deploy regression vs dependency vs config vs traffic shape.
3. Escalate when credentials, access, or org policy blocks verification.

## Stop when

- `RESOLVED` with verified fix (when a fix was in scope), or
- `ESCALATED` with a clear reason.

Summarize: unknown, root cause, evidence, case id, whether a fix was applied, and the `issues/` path.

Event schemas: [../debugging-engine-investigate/reference.md](../debugging-engine-investigate/reference.md).

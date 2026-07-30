---
name: debugging-engine-incident
description: >-
  Fixes bugs and production incidents with Debugging Engine: investigate if needed,
  then Implementer patches, verify, FixAccepted. Use for SEV/outages,
  production failures, or when the user asks to fix an issue already reported under
  issues/. For report-only root-cause work use debugging-engine-investigate.
disable-model-invocation: true
---

# Debugging Engine Incident

You are the **coding-agent brain** for Debugging Engine in **fix** mode. Same kernel as [debugging-engine-investigate](../debugging-engine-investigate/SKILL.md), but you **may** propose interventions, act as Implementer, and verify fixes.

Prefer starting from an existing `issues/<slug>.md` brief (from investigate). If missing, write one first (impact, start time, deploys, blast radius, success criteria), then `open` it.

## Open modes

```bash
debugging-engine open issues/<slug>.md --mode incident      # default; local fix path
debugging-engine open issues/<slug>.md --mode production   # Human + org gates
```

| Mode | Extra gates |
| --- | --- |
| `incident` | `RootCauseAccepted` then `FixAccepted` when interventions exist |
| `production` | Human `approve` for HIGH/CRITICAL interventions before `ExperimentApproved`; `OrgApprovalReceived` before `FixAccepted` |

## Rules (in addition to investigate kernel rules)

1. Follow Judge Tasks for Analyst / Adversary / Implementer / Verifier / Judge.
2. Prefer **observational** experiments first; then propose `experiment_class=intervention` with a contained `patch` when evidence supports a fix.
3. Mark production/risky interventions `cost: HIGH` or `CRITICAL`; escalate if policy or access blocks them.
4. Completion: `RootCauseAccepted` (cause) then `FixAccepted` (verified fix) when any intervention/patch exists. Both are Judge-only with `authority: Judge`.
5. Competing hypotheses must be rejected or suspended before accept.
6. After new SUPPORTS evidence, expect Adversary rebuttal before approve/accept.
7. Event `producer` must match Task `role`. Never forge Adversary/Implementer/Human producers.
8. **Human is the real user (mandatory stop):** When `next` returns `role: Human`, announce the handoff, **stop**, and ask the user. Do **not** submit `HumanResponseReceived` or `OrgApprovalReceived` yourself. Wait for an explicit yes/no (or tell them to run the CLI below). Auto-approving as Human is a rule violation.
9. **Visible handoffs (mandatory):** After every `debugging-engine next`, before any `submit` / `verify` / patch work, print:

```text
**Role: <role>** — <objective>
```

Announce **Judge every time** they approve, accept cause, or accept fix. Announce **Verifier** before every `verify`, **Implementer** before every `PatchApplied`, and **Human** before pausing for the user. Silent role turns are a rule violation.

## Loop

```text
open issues/<slug>.md --mode incident|production → next → …
  → Adversary → Judge approve → Verifier (observe) → interpret → …
  → Judge RootCauseAccepted (cause; may stay ACTIVE)
  → Analyst proposes intervention → (production: STOP for real Human approve)
  → Judge approve → Implementer (PatchApplied) → Verifier → interpret → …
  → (production: STOP for real Human OrgApproval)
  → Judge FixAccepted → RESOLVED
  → or Escalated (groundbreaking / safety / human-only / blocked access)
```

### Role work

- **Analyst:** hypotheses + experiments; after supporting evidence, propose intervention patches (do not self-approve or apply them as Analyst).
- **Adversary:** competing hypotheses/interpretations; announce every handoff.
- **Implementer:** announce, then materialize approved patches; submit `PatchApplied`.
- **Verifier:** announce, then `debugging-engine verify <case-id> <experiment-id>`.
- **Human (real user):** announce, then **pause**. Prefer:

```bash
debugging-engine human-approve <case-id> <experiment-id> --decision approve   # or reject
debugging-engine org-approve <case-id> --rationale "…"
```

  Only after the user has approved (CLI or explicit chat “approve”) may you continue with `next`.
- **Judge:** announce, then approve / RootCauseAccepted / FixAccepted / escalate — once per Task, every Task. Never submit Human events as Judge.

## Production extras

1. Capture SEV symptoms: impact, start time, recent deploys, dashboards, blast radius.
2. Competing hypotheses should include deploy regression vs dependency vs config vs traffic shape.
3. Open with `--mode production` when changes need org/human gates.
4. Escalate when credentials, access, or org policy blocks verification.
5. Never invent Human approvals to “keep the loop moving.”

## Stop when

- `RESOLVED` with `FixAccepted` (when a fix was in scope), or
- `RESOLVED` with `RootCauseAccepted` only if no intervention was ever proposed (rare for this skill), or
- `ESCALATED` with a clear reason,
- **or** waiting on Human — stop the turn and ask the user (not a case terminal, but an agent stop).

Summarize: unknown, root cause, evidence, case id, whether a fix was applied, mode, and the `issues/` path.

Event schemas: [../debugging-engine-investigate/reference.md](../debugging-engine-investigate/reference.md).

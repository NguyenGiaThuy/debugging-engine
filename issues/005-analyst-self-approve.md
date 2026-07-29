# Analyst proposes then self-approves / self-implements

## Symptoms
During live investigations, the coding agent stays on **Role: Analyst** from hypothesis proposal through claim confirmation and code implementation. There is no Judge handoff to approve experiments, no Verifier/Implementer scheduling, and no Adversary challenge before the Analyst declares claims confirmed and implements a fix.

Observed chat pattern (single Analyst segment):
1. `Role: Analyst — Proposing hypotheses and experiments…`
2. Edits source files and runs commands (experiments executed under Analyst)
3. `Role: Analyst — Claims confirmed. Implementing …`

Expected flow: Analyst proposes only → Judge reviews and schedules Verifier/Implementer and Adversary challenge → **Judge** (not Analyst) approves → then implementation proceeds under the assigned roles.

## Success criteria
- After Analyst submits HypothesisProposed / ExperimentProposed, `next` does not leave the agent free to approve or implement as Analyst.
- Judge is the only role scheduled to emit `ExperimentApproved`.
- Adversary challenge and Verifier/Implementer execution are scheduled by Judge policy before claims are treated as confirmed / root cause accepted.
- Skill and/or kernel enforce: Analyst must not self-confirm claims or apply intervention patches without those handoffs.
- Regression tests cover the post-propose scheduling path; suite green; fix applied and verified.

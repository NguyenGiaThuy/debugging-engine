---
name: debugging-engine-incident
description: >-
  Investigates production incidents and outages using the Debugging Engine investigation
  kernel (Case State, experiments, evidence). Use when the user reports an
  incident, outage, production failure, SEV, or asks for incident root-cause
  analysis with Debugging Engine.
disable-model-invocation: true
---

# Debugging Engine Incident

Same kernel as [debugging-engine-investigate](../debugging-engine-investigate/SKILL.md). Specialize the Unknown and experiments for **production incidents**.

## Extra guidance

1. Capture symptoms as an issue markdown: impact, start time, recent deploys, dashboards, blast radius.
2. Prefer **observational** experiments first (logs, metrics, traces) before interventions.
3. Mark production interventions `cost: HIGH` or `CRITICAL`; escalate if policy blocks them.
4. Competing hypotheses should include deploy regression vs dependency vs config vs traffic shape.
5. Escalate when access, credentials, or org policy blocks verification.

## Loop

Follow the investigate skill loop: `open` → `next` → work → `submit`/`verify` → resolve or escalate.

Event schemas: [../debugging-engine-investigate/reference.md](../debugging-engine-investigate/reference.md).

# Roadmap

SMADW is architecture (an investigation kernel). Skills and IDE wrappers come last.

## Phase 1 — Runtime MVP (done)

Minimal agent-agnostic Python CLI kernel: domain model, JSONL Event Log, Case State projection, Judge task handoff, in-engine Verifier, seeded `subject/` defects, stub e2e.

## Phase 2 — Validate the architecture (current)

Ask which architectural assumptions are wrong. Record findings as ADRs in [`decisions/`](decisions/).

Harness: `smadw validate` runs stress scenarios (happy path, hypothesis flood, starvation, evidence bloat) and writes [`validation/phase2-report.md`](validation/phase2-report.md).

## Phase 3 — Framework

Stabilize APIs so others can build on SMADW (`Case.Create`, projections, scheduling policies).

## Phase 4 — Skills / interfaces

Only then wrap the kernel as skills (“Investigate this issue”, etc.). SMADW remains the engine.

## Explicit non-goals (until later)

- Embedding LLM provider SDKs in the kernel
- Hive / multi-agent colony integration
- Distributed Event Bus (Kafka, etc.)
- Knowledge learning pipeline (Level 3)

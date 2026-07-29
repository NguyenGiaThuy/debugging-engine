# Roadmap

SMADW is architecture (an investigation kernel). Skills and IDE wrappers come last.

## Phase 1 — Runtime MVP (current)

Build the smallest agent-agnostic system that faithfully implements the architecture:

- Domain model + Event Log + Case State projection
- Judge scheduling + Task handoff
- CLI contract for any coding agent
- In-engine Verifier (pytest / Verification Specs)
- Seeded `subject/` defects for validation
- Deterministic stubs for CI e2e (not a product LLM path)

**Success:** Can a coding agent (or stubs) investigate a real defect via SMADW better than unstructured chat?

## Phase 2 — Validate the architecture

Ask which assumptions are wrong. Record findings as ADRs in [`decisions/`](decisions/).

Examples: Judge over/under-informed, Analyst hypothesis flood, Case State bloat, Event Log growth.

## Phase 3 — Framework

Stabilize APIs so others can build on SMADW (`Case.Create`, projections, scheduling policies).

## Phase 4 — Skills / interfaces

Only then wrap the kernel:

- “Investigate this issue”
- “Find performance bottleneck”
- “Production incident”

SMADW remains the engine; skills are interfaces—like Git vs GitHub Desktop.

## Explicit non-goals (until later)

- Embedding LLM provider SDKs in the kernel
- Hive / multi-agent colony integration
- Distributed Event Bus (Kafka, etc.)
- Knowledge learning pipeline (Level 3)

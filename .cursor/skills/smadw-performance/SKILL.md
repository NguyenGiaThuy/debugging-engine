---
name: smadw-performance
description: >-
  Finds performance bottlenecks (latency, throughput, memory, CPU) using the
  SMADW investigation kernel with measurement-first experiments. Use when the
  user asks about slow endpoints, latency regressions, memory growth, or
  performance root cause with SMADW.
disable-model-invocation: true
---

# SMADW Performance

Same kernel as [smadw-investigate](../smadw-investigate/SKILL.md). Specialize for **performance unknowns**.

## Extra guidance

1. Unknowns must be measurable (e.g. “Why did p99 latency rise after deploy X?”).
2. Every experiment needs a Verification Spec with metrics/thresholds or a benchmark/pytest gate.
3. Prefer HIGH information-gain / LOW cost measurements (profiles, benchmarks) before speculative rewrites.
4. Keep observation vs interpretation separate: numbers are evidence; “Redis contention” is interpretation.
5. Discriminate competing causes with paired experiments (baseline → change one variable).

## Loop

Follow the investigate skill loop: `open` → `next` → measure → `submit`/`verify` → resolve or escalate.

Event schemas: [../smadw-investigate/reference.md](../smadw-investigate/reference.md).

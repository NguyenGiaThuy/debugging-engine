# ADR 0004 — Judge must not use content heuristics

## Context

Phase 1 Judge code inspected hypothesis titles/explanations for substrings like `"logging"` / `"alternative"` to decide Adversary involvement. That is technical content sniffing and contradicts Part II (Judge is meta-technical).

## Decision

Remove all natural-language content heuristics from the Judge. Adversary invocation is based solely on structural Case State (counts of competing hypotheses, presence of evidence/interpretations, budgets, stall cycles).

## Rationale

Preserves exclusive responsibilities and keeps the Judge replaceable without embedding debugging knowledge.

## Consequences

- Competing-hypothesis detection is structural (`len(competing) < 2`), not semantic.
- Quality of alternative hypotheses remains the Adversary/coding-agent’s job.

## Alternatives considered

- LLM-based Judge critique — rejected; would embed a model and violate agent-agnostic kernel design.

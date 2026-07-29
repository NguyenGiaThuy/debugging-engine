# ADR 0002 — Hypothesis budget per Unknown

## Context

Nothing prevented Analyst/Adversary from emitting unbounded `HypothesisProposed` events. The Judge never constrained explanatory proliferation, risking hypothesis lock-in volume without corresponding experiments (`hypothesis_flood` scenario).

## Decision

Each Unknown may have at most `MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN` (5) **active** hypotheses (excluding REJECTED, SUSPENDED, ACCEPTED). Further `HypothesisProposed` events fail validation. When the budget is exhausted, the Judge asks for discriminating experiments instead of more hypotheses.

## Rationale

Unknowns define scope; hypotheses exist to explain them. A soft budget forces discrimination via experiments (Part I Principles 1–2) without introducing numerical confidence.

## Consequences

- Stub and coding-agent workflows must reject/suspend hypotheses before proposing more once at the cap.
- ValidationError on submit is the enforcement point (kernel-level, not prompt-level).

## Alternatives considered

- Soft warnings only — rejected; agents can ignore warnings.
- Global case-wide cap — rejected; multi-Unknown cases need per-Unknown budgets.

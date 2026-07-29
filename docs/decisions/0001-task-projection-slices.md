# ADR 0001 — Task projection slices and evidence truncation

## Context

Phase 1 Task handoffs dumped near-complete registries (full explanations, patches, pytest stdout) into `debugging-engine next` projections. Evidence events stored multi-kilobyte verification transcripts. This violates Part III §15 (agents request views, not full Case State) and caused measurable Event Log growth in the `evidence_bloat` scenario.

## Decision

1. Task projections are **role-minimal summaries**: ids, short titles, statuses, and compact metrics — not full explanations, patches, or raw logs.
2. Verification observations are truncated to `MAX_OBSERVATION_CHARS` (2048) with `attributes.observation_truncated` and `raw_observation_chars` recorded.

## Rationale

Coding agents need enough structure to act, not the entire investigation history on every turn. Truncation preserves auditability of pass/fail while bounding log size.

## Consequences

- Agents must `debugging-engine query` for deeper detail when needed.
- Full pytest output is not reconstructible from Evidence alone (exit codes and truncated tails remain).

## Alternatives considered

- Compress full payloads in the Event Log — rejected; still forces agents to ingest large projections.
- Store artifacts on disk with URI references — deferred to a later phase.

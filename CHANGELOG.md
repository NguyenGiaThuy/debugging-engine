# Changelog

All notable changes to the **debugging-engine** package are recorded here.
The architecture specification remains **Debugging Engine v1.0.0** (`docs/SPECIFICATION.md`);
package versions below are kernel / CLI releases that implement subsets of that spec.

## [1.0.11] — 2026-07-30

### Changed
- Human production gates are **real-user only**: skills/Judge hints require the agent to stop and ask; do not auto-submit Human/OrgApproval events.
- CLI: `human-approve` and `org-approve` for explicit user approvals.

## [1.0.10] — 2026-07-30

### Added
- **M1–M3 investigation modes:** `open --mode investigate|incident|production` (default `incident`).
- `FixAccepted` and `OrgApprovalReceived` events; Case State tracks `mode` and `accepted_root_cause_id`.
- Production: Human `approval_for` + `decision=approve` required before approving HIGH/CRITICAL interventions; org approval required before `FixAccepted`.
- Incident scene `issues/010` + `scenes/retry_budget/` for production-mode practice.

### Changed
- `RootCauseAccepted` proves cause only; resolves immediately in `investigate` (or incident with no interventions). Fix path completes via `FixAccepted`.
- Investigate mode rejects intervention/patch experiments at propose/approve.

## [1.0.9] — 2026-07-30

### Changed
- Skills require a visible `**Role: <role>** — <objective>` line after every `next` (including every Judge/Verifier turn).
- Judge Task `hints` always include `ANNOUNCE_HANDOFF_HINT` so projections reinforce the chat handoff rule.

### Added
- Incident scene `issues/009` + `scenes/rate_limit/` (token bucket never refills; fixed via elapsed-time refill).

## [1.0.8] — 2026-07-30

### Changed
- **Investigate vs incident skills:** investigate is report-only (observational `RootCauseAccepted` + `issues/` write-up); incident owns Implementer/fix.
- Judge no longer forces intervention before accept when none was proposed (`report_only` path).
- **K1** Rich Verification Spec: optional `metrics` / `thresholds` / `baselines`; verify parses `name=value` stdout lines.
- **K2** Adversary must supply `objection_category` on hypotheses/interpretations.
- **K3/K4** `UnknownPartiallyResolved` + `parent_unknown` / `child_unknowns` wiring.
- **K5** Per-object `revision` on Unknown/Hypothesis/Experiment/Evidence/Interpretation.
- **K6** `SyncJsonlEventBus` / `AsyncQueueEventBus` abstraction.
- **K7** `Human` role + `HumanResponseReceived`; stall schedules Human before Judge escalate.
- **K8** `status()` defaults to projection summary; `status(full=True)` / `query("full")` for full dump.

## [1.0.7] — 2026-07-30

### Changed
- Consistency pass: skills/`reference.md` document full RootCause, producer↔role, path containment, and verify→FAILED gates.
- README / API / SPEC note package vs architecture version; issues 001–005 marked fixed/closed.
- Added `CHANGELOG.md`.

## [1.0.6] — 2026-07-30

### Fixed
- Webhook dedupe incident scene: idempotency key now includes canonical payload so status corrections for the same `event_id` deliver while identical retries still collide.

## [1.0.5] — 2026-07-30

### Added
- Incident scene `issues/008` + `scenes/webhook_dedupe/` (event-id-only key bug).

### Fixed
- Submit requires `event.producer` to match the current Judge Task `role` (blocks forging `producer: Adversary` on Analyst tasks to skip dialectic).

## [1.0.4] — 2026-07-30

### Changed
- Judge re-engages **Adversary** when SUPPORTS evidence lacks an Adversary interpretation (at most once per evidence id).
- `RootCauseAccepted` requires Judge producer + `authority: Judge`, supporting interpretations, all terminal evidence interpreted, at least one passed verification, successful intervention when any patched/intervention experiment exists, and disposed competitors.
- Escaping `patch` paths rejected at `ExperimentProposed`.

## [1.0.3] — 2026-07-29

### Fixed
- Path containment for patches and verification `working_directory`.
- Unexpected verify exit → experiment **FAILED** (not COMPLETED).
- Submit enforced against last Task `allowed_event_types`; `PatchApplied` Implementer/Verifier-only.
- Optional hypothesis `parent_id` with cascade reject/suspend.
- `pytest` included so `demo` / `verify` work under `uv tool install`.

## [1.0.2] and earlier

Initial public kernel + CLI: Case State, Event Log, Judge scheduling (single Task), skills scaffold, offline `demo` / `validate`.

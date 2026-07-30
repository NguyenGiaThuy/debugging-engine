# SEV-2: Payment SDK retry storm after partner 5xx

## Status

**Incident RESOLVED.** Root cause accepted; **fix applied and verified** (production mode).

| Field | Value |
| --- | --- |
| `case_id` (production) | `e8d46c43-02b5-4e24-b299-91dde3a0749e` |
| Accepted hypothesis | `RetryBudget.run` never increments spent (`7798c024-c251-41ee-8285-a50b3b505d9b`) |
| Intervention | `18e393a0-86a9-4d25-bad2-223c326ce1e4` — increment spent, exhaust, internal retry to `succeed_on_attempt` |

## Impact

- `payments-api` outbound client retries partner tax quotes forever when the partner returns intermittent 5xx.
- Thread pool saturation; checkout p99 climbs; secondary 429s from our own rate limits.
- Revenue-impacting for carts that need live tax quotes.

## Start time

- First alert: **2026-07-30 03:05 UTC** (`OutboundRetryStorm`, PagerDuty).
- Correlates with `payments-sdk` v1.8.0 “simplify retry budget” change.

## Accepted root cause

`RetryBudget.run` in `scenes/retry_budget/budget.py` (stand-in for payments-sdk v1.8.0) **read** `_spent` but **never wrote** it on failure. Each call reported `attempts=1`, `exhausted=False` with `_spent={}`, so callers never fail-fast and retry forever under partner 5xx. Default `max_attempts=3` was finite; the defect was accounting, not config or op_id isolation.

## Fix applied

Persist spent on failure, return `exhausted` when `attempt >= max_attempts`, fail-fast when already exhausted, and when `succeed_on_attempt` is set loop within `run` until success or budget exhaustion (reset spent on success).

## Key evidence

1. **Pre-fix suite** (`pytest scenes/retry_budget/tests/test_budget.py`): `3 failed` — exhaustion never set; in-call success never reached.
2. **Passed observational probe**: five failures left `_spent={}`, `attempts` always `1`, `exhausted` always `False` with `max_attempts=3`.
3. **Post-fix suite**: `3 passed` after intervention.

## Competing hypotheses

| Hypothesis | Disposition |
| --- | --- |
| `max_attempts` misconfigured to unbounded | **REJECTED** (`max_attempts=3` observed) |
| Storm only for a subset of `op_id` keys | **REJECTED** (all ops fail to exhaust) |
| `exhausted` flag never set even when spent increments | **REJECTED** (spent never increments) |

## Success criteria

- [x] Observational evidence proves the budget never exhausts.
- [x] Competing hypotheses rejected/suspended.
- [x] `RootCauseAccepted`, verified intervention, `OrgApprovalReceived`, then `FixAccepted`.
- [x] `scenes/retry_budget/tests/test_budget.py` passes after the fix.

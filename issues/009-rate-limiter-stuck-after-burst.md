# SEV-2: Legitimate clients stuck behind rate limiter after burst

## Status

**Incident RESOLVED.** Root cause accepted; **fix applied and verified**.

| Field | Value |
| --- | --- |
| `case_id` (incident) | `5ed5f372-146c-432f-a6d1-173eb5bdc853` |
| Prior investigate `case_id` | `7d518b6e-d31d-4b87-82bb-08d820fc614c` |
| Accepted hypothesis | `TokenBucket.allow` never refills from elapsed time (`f69d5b06-2ae5-49e3-94c3-984fb470d911`) |
| Intervention | `9118064d-824b-437d-9f9b-c65553adaf68` — restore elapsed-time refill |

## Impact

- Edge gateway returns `429 Too Many Requests` for ~8% of authenticated API traffic even when clients stay under the published 60 req/min budget.
- Support: partners report “works for a few calls then permanently blocked until process restart.”
- Payment webhooks and checkout reads share the same limiter keyspace (`client_id`).
- No upstream 5xx spike; origin services are healthy.

## Start time

- First partner alert: **2026-07-30 02:10 UTC**.
- Correlates with `edge-gateway` v3.2.1 deploy that “simplified” the in-process token bucket.

## Accepted root cause

`TokenBucket.allow` in `scenes/rate_limit/limiter.py` (stand-in for the v3.2.1 refill rewrite) read `last_refill_ms` but **ignored it** and never added tokens from `(now_ms - last_ms) * refill_per_second`. After the burst window was spent, `remaining` stayed `0` for that key until process restart — matching permanent 429s and deny logs minutes after idle.

## Fix applied

Restored continuous refill in `scenes/rate_limit/limiter.py`:

```python
elapsed_sec = max(0.0, (now_ms - last_ms) / 1000.0)
tokens = min(float(self.capacity), tokens + elapsed_sec * self.refill_per_second)
```

## Key evidence

1. **Pre-fix suite** (`pytest scenes/rate_limit/tests/test_limiter.py`): `1 failed, 2 passed` — only `test_refill_allows_traffic_after_wait` failed (`allowed=False`, `remaining=0` at `t0+1500ms`); burst and key isolation passed.
2. **Passed observational probe**: after burst, `allow` at `t0+3_600_000ms` still denied with `remaining=0` (`sticky_zero_confirmed`) → rules out unit-scale under-refill.
3. **Post-fix suite**: `3 passed` after intervention restoring elapsed refill.

## Competing hypotheses

| Hypothesis | Disposition |
| --- | --- |
| `rate_limit_v2` store never expires keys | **SUSPENDED** (local in-process repro does not exercise the flag path) |
| Partners share one `client_id` (collision) | **REJECTED** (keys isolated while single key stuck at 0) |
| Refill math uses wrong time units | **REJECTED** (1h wait still `remaining=0`) |

## Success criteria

- [x] `python -m pytest scenes/rate_limit/tests/test_limiter.py -q` passes.
- [x] After burst exhaustion, waiting restores tokens; keys remain isolated.

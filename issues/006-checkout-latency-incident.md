# SEV-2: Checkout API p99 latency spike

## Impact

- ~18% of checkout `POST /v1/checkout` requests exceed the 2s SLO (p99 jumped from ~400ms to ~3.1s).
- Error rate elevated but not catastrophic: `5xx` ~1.4% (baseline ~0.2%).
- Revenue-impacting for web + iOS checkout; Android appears less affected (lower traffic).

## Start time

- First alert: **2026-07-29 16:42 UTC** (`CheckoutP99High`, PagerDuty).
- Customer reports started ~16:50 UTC.
- Still ongoing as of investigation open.

## Recent deploys

| Time (UTC) | Change | Service |
| --- | --- | --- |
| 16:10 | `payments-api` v2.14.0 — “optimize tax quote cache” | payments-api |
| 15:55 | `edge-gateway` config: raise idle timeout 30s → 60s | edge |
| 14:02 | `inventory-service` routine dependency bump (no code) | inventory |
| Yesterday | Redis cluster maintenance window (completed 22:00 UTC) | shared-cache |

## Dashboards / signals

- Grafana: Checkout RED dashboard — latency + saturation on `payments-api`.
- Datadog APM: span `TaxQuote.Get` dominates p99; DB spans look normal.
- Logs: intermittent `RedisTimeout waiting for connection` from `payments-api` pods in `us-east-1a` only.
- Metrics: Redis `connected_clients` flat; `evicted_keys` slightly up after 16:10.
- Feature flag `tax_quote_v2` rolled to **25%** at 16:08 (same window as deploy).

## Blast radius

- Region: primarily `us-east-1` (EU traffic near baseline).
- Cohort: users with cart tax calculation enabled (most US carts).
- Not affecting browse/search or order-history APIs.

## Open unknowns

1. Is this a deploy regression in `payments-api` v2.14.0 tax-cache change?
2. Is Redis / cache saturation or connection pool exhaustion the proximate cause?
3. Is the feature flag `tax_quote_v2` shaping bad traffic onto a slow path?
4. Is the edge-gateway idle-timeout change related?
5. Regional / AZ issue (`us-east-1a`) vs cluster-wide?

## Constraints

- Prefer observational experiments first (logs, metrics, traces, flag percentage) before interventions.
- Production interventions (flag rollback, deploy rollback, Redis restart) are `cost: HIGH` or `CRITICAL`.
- Escalate when access, credentials, or org policy blocks verification.

## Success criteria

- p99 for `POST /v1/checkout` back under 2s SLO in `us-east-1`.
- `5xx` rate returned to baseline (~0.2%).
- Root cause identified with evidence; competing explanations disposed or rejected.
- Safe mitigation applied or explicitly escalated if production changes are blocked.

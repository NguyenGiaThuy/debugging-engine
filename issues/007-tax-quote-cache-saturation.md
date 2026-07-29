# SEV-2: Checkout p99 driven by TaxQuote.Get cache misses

## Impact

- `POST /v1/checkout` p99 remains above the 2s SLO in `us-east-1` (~2.8–3.4s).
- Datadog APM attributes most of the excess to span `TaxQuote.Get` (p99 ~2.1s); payment capture and inventory holds are near baseline.
- `5xx` ~0.9% on checkout (baseline ~0.2%), concentrated on carts that cross tax jurisdictions (gift / multi-ship).
- Web + iOS checkout conversion down ~6% hour-over-hour.

## Start time

- Recurrence of elevated `TaxQuote.Get` latency starting **2026-07-29 17:05 UTC**, after the earlier CheckoutP99High page at 16:42.
- Correlates with rising share of multi-region carts in US evening traffic.

## Recent deploys

| Time (UTC) | Change | Service |
| --- | --- | --- |
| 16:10 | `payments-api` v2.14.0 — “optimize tax quote cache” | payments-api |
| 16:08 | Feature flag `tax_quote_v2` → 25% | config |
| 17:01 | Flag raised to **40%** (on-call attempt to “stabilize”) | config |

## Dashboards / signals

- APM: `TaxQuote.Get` compute path dominates; cache-hit ratio on the tax-quote Redis keyspace fell from ~92% to ~61% after 16:10.
- Logs: `tax_quote cache_miss cart_id=… region=EU` immediately after a US quote for the same `cart_id`.
- Metrics: Redis CPU normal; `evicted_keys` only slightly elevated — does **not** look like cluster saturation alone.
- Local reproduction target in this repo: `scenes/checkout_tax_quote/` (unit tests under `scenes/checkout_tax_quote/tests/`).

## Blast radius

- Carts that request tax for more than one `region` (US/EU gift flows, cross-border).
- Single-region carts mostly fine (explains why Android, lower gift mix, looked healthier).

## Open unknowns

1. Did v2.14.0 change cache key composition so region is ignored or collapsed?
2. Is `tax_quote_v2` selecting a code path with different cache semantics?
3. Are we seeing true Redis faults, or application-level key collisions forcing cold computes?
4. Would killing the flag or rolling back v2.14.0 restore hit ratio without a code fix?

## Constraints

- Prefer observational experiments first (reproduce with unit tests / metrics) before production rollback.
- Flag kill-switch or deploy rollback is `cost: HIGH`.
- A local code fix in `scenes/checkout_tax_quote/` is acceptable once evidence supports the cache-key hypothesis; mark that intervention `cost: LOW` relative to prod rollback.

## Success criteria

- `python -m pytest scenes/checkout_tax_quote/tests/test_tax_quote.py -q` passes.
- Cache keys distinguish `(cart_id, region)` (or equivalent); US/EU quotes never overwrite each other.
- Checkout TaxQuote cold-path rate explained; competing Redis-saturation-only hypothesis weakened or rejected.
- Production HIGH-cost mitigations only if local fix is insufficient or blocked.

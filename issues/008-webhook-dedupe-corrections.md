# SEV-2: Paid webhooks stuck as pending for partner reconciler

## Impact

- Partner reconciler shows ~12% of `order.updated` webhooks stuck with `status=pending` after the customer already paid.
- Support volume: ~40 tickets/hour claiming “paid in app, partner still unpaid.”
- Finance: delayed settlement flags on the partner ledger; no card-capture failures on our side.
- Checkout UI and `/v1/checkout` latency are healthy (unlike the TaxQuote incident).

## Start time

- First partner alert: **2026-07-30 00:18 UTC**.
- Correlates with a spike in “status correction” traffic after the 23:50 UTC payments-api deploy that retries failed webhook posts with an updated body.

## Recent deploys

| Time (UTC) | Change | Service |
| --- | --- | --- |
| 23:50 | `payments-api` v2.14.3 — retry webhook delivery with corrected payload on upstream 5xx | payments-api |
| 22:10 | `partner-gateway` connection pool tune | partner-gateway |
| 20:00 | Feature flag `webhook_dedupe_v2` → 50% | config |

## Dashboards / signals

- APM: `WebhookDispatcher.deliver` success rate ~99%, but partner ingress shows missing `status=paid` bodies for the same `event_id`.
- Logs: `webhook deduped event_id=evt-…` immediately after `payload.status` changed from `pending` → `paid`.
- Metrics: upstream timeout rate elevated for 8 minutes after deploy, then normal; dedupe counter kept climbing.
- Local reproduction: `scenes/webhook_dedupe/` (`tests/test_webhook.py`).

## Blast radius

- Partners on the reconciler path that require the final `paid` body.
- Orders that hit a transient upstream timeout on the first attempt, then a corrected retry.
- Idempotent identical retries should still dedupe (no double-charge risk desired).

## Open unknowns

1. Does idempotency key ignore payload and key only on `event_id`?
2. Is `webhook_dedupe_v2` selecting a stricter dedupe store?
3. Are partners dropping corrected bodies, or are we never sending them?
4. Would disabling the flag restore corrections without a code fix?

## Constraints

- Prefer observational experiments first (unit tests / log correlation) before flag kill or deploy rollback.
- Flag kill / prod rollback is `cost: HIGH`.
- Local fix under `scenes/webhook_dedupe/` is `cost: LOW` once evidence supports a key-composition bug.

## Success criteria

- `python -m pytest scenes/webhook_dedupe/tests/test_webhook.py -q` passes.
- Corrected payloads for the same `event_id` are delivered; identical retries remain deduped.
- Competing “partner-only drop” / flag-only hypotheses are weakened or rejected with evidence.

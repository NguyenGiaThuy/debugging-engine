# Session expires despite recent activity

## Symptoms

- Users report being logged out while actively using the product (clicking, saving drafts).
- Server metrics show `session_expired` rising even when `touch` is called regularly.
- Repro is intermittent: short sessions look fine; longer interactive sessions fail.

## Observed behavior

1. Create session at `t=0` with TTL=10s.
2. Call `touch` at `t=8`.
3. At `t=15` (7s after last touch), `is_active` returns `False`.
4. Expected: still active because last activity was within TTL.

## Success criteria

- `tests/test_session.py` passes (especially `test_touch_extends_session_lifetime` and `test_repeated_touch_keeps_long_lived_session`).
- Expiry is based on last activity, not only session creation time.
- No change to TTL configuration semantics beyond using the correct timestamp.

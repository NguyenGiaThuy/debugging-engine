"""Regression tests for token-bucket rate limiting."""

from __future__ import annotations

from limiter import TokenBucket


def test_burst_allows_up_to_capacity() -> None:
    bucket = TokenBucket(capacity=3, refill_per_second=1.0)
    t = 1_000_000.0
    assert bucket.allow("user-a", now_ms=t).allowed is True
    assert bucket.allow("user-a", now_ms=t).allowed is True
    assert bucket.allow("user-a", now_ms=t).allowed is True
    assert bucket.allow("user-a", now_ms=t).allowed is False


def test_refill_allows_traffic_after_wait() -> None:
    """After capacity is spent, waiting should restore tokens via refill."""
    bucket = TokenBucket(capacity=2, refill_per_second=2.0)
    t0 = 2_000_000.0
    assert bucket.allow("user-b", now_ms=t0).allowed is True
    assert bucket.allow("user-b", now_ms=t0).allowed is True
    assert bucket.allow("user-b", now_ms=t0).allowed is False
    # 1.5s later at 2 tokens/sec → ~3 tokens worth of refill (capped at capacity).
    later = bucket.allow("user-b", now_ms=t0 + 1500.0)
    assert later.allowed is True
    assert later.remaining >= 0


def test_keys_are_isolated() -> None:
    bucket = TokenBucket(capacity=1, refill_per_second=0.0)
    t = 3_000_000.0
    assert bucket.allow("a", now_ms=t).allowed is True
    assert bucket.allow("a", now_ms=t).allowed is False
    assert bucket.allow("b", now_ms=t).allowed is True

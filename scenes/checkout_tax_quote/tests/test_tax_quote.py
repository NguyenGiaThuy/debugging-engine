"""Regression tests mirroring checkout TaxQuote.Get latency / correctness."""

from __future__ import annotations

from tax_quote import TaxQuoteCache, TaxQuoteService


def test_cache_hit_avoids_recompute() -> None:
    cache = TaxQuoteCache()
    svc = TaxQuoteService(cache)
    q1 = svc.get_quote("cart-1", 10_000, "US")
    q2 = svc.get_quote("cart-1", 10_000, "US")
    assert q1 == q2
    assert cache.compute_calls == 1
    assert cache.hits >= 1


def test_same_cart_different_regions_do_not_share_quote() -> None:
    """US and EU tax rates differ; cache must not return the wrong region."""
    cache = TaxQuoteCache()
    svc = TaxQuoteService(cache)
    us = svc.get_quote("cart-9", 10_000, "US")
    eu = svc.get_quote("cart-9", 10_000, "EU")
    assert us.rate_bps != eu.rate_bps
    assert us.tax_cents != eu.tax_cents
    # Two regions => two computes if keys are correct; a buggy shared key yields 1.
    assert cache.compute_calls == 2


def test_region_switch_under_load_stays_correct() -> None:
    cache = TaxQuoteCache()
    svc = TaxQuoteService(cache)
    # Simulate interleaved checkout traffic for one cart id across regions.
    quotes = [
        svc.get_quote("cart-42", 5_000, "US"),
        svc.get_quote("cart-42", 5_000, "EU"),
        svc.get_quote("cart-42", 5_000, "US"),
        svc.get_quote("cart-42", 5_000, "EU"),
    ]
    assert quotes[0].rate_bps == 875
    assert quotes[1].rate_bps == 2000
    assert quotes[2].rate_bps == 875
    assert quotes[3].rate_bps == 2000
    assert cache.misses >= 2

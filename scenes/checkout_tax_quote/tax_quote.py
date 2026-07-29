"""Tax quote helper used by checkout (local stand-in for payments-api TaxQuote path)."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class TaxQuote:
    amount_cents: int
    rate_bps: int
    tax_cents: int


class TaxQuoteCache:
    """In-process cache standing in for the shared Redis tax-quote cache."""

    def __init__(self) -> None:
        self._store: dict[str, TaxQuote] = {}
        self.misses = 0
        self.hits = 0
        self.compute_calls = 0

    def _key(self, cart_id: str, region: str) -> str:
        # Include region so multi-jurisdiction carts do not collide or return wrong rates.
        return f"{cart_id}:{region.upper()}"

    def get(self, cart_id: str, region: str) -> TaxQuote | None:
        key = self._key(cart_id, region)
        quote = self._store.get(key)
        if quote is None:
            self.misses += 1
            return None
        self.hits += 1
        return quote

    def set(self, cart_id: str, region: str, quote: TaxQuote) -> None:
        self._store[self._key(cart_id, region)] = quote


def compute_tax(amount_cents: int, region: str) -> TaxQuote:
    """Expensive stand-in for upstream tax authority + DB work."""
    time.sleep(0.05)  # ~50ms cold path
    rate_bps = 875 if region.upper() == "US" else 2000
    tax_cents = amount_cents * rate_bps // 10_000
    return TaxQuote(amount_cents=amount_cents, rate_bps=rate_bps, tax_cents=tax_cents)


class TaxQuoteService:
    def __init__(self, cache: TaxQuoteCache | None = None) -> None:
        self.cache = cache or TaxQuoteCache()

    def get_quote(self, cart_id: str, amount_cents: int, region: str) -> TaxQuote:
        cached = self.cache.get(cart_id, region)
        if cached is not None and cached.amount_cents == amount_cents:
            return cached
        self.cache.compute_calls += 1
        quote = compute_tax(amount_cents, region)
        self.cache.set(cart_id, region, quote)
        return quote

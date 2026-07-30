"""In-process API rate limiter (local stand-in for edge gateway)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_ms: int = 0


@dataclass
class TokenBucket:
    """Per-key token bucket.

    Tokens should refill continuously based on ``now_ms`` so steady low-rate
    traffic is never blocked after the initial burst.
    """

    capacity: int = 5
    refill_per_second: float = 1.0
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict)
    # key -> (tokens, last_refill_ms)

    def allow(self, key: str, *, now_ms: float, cost: float = 1.0) -> RateLimitResult:
        tokens, last_ms = self._buckets.get(key, (float(self.capacity), now_ms))
        elapsed_sec = max(0.0, (now_ms - last_ms) / 1000.0)
        tokens = min(float(self.capacity), tokens + elapsed_sec * self.refill_per_second)
        if tokens < cost:
            self._buckets[key] = (tokens, now_ms)
            retry = 0 if self.refill_per_second <= 0 else int(max(1.0, (cost - tokens) / self.refill_per_second * 1000.0))
            return RateLimitResult(allowed=False, remaining=int(tokens), retry_after_ms=retry or 1000)
        tokens -= cost
        self._buckets[key] = (tokens, now_ms)
        return RateLimitResult(allowed=True, remaining=int(tokens), retry_after_ms=0)

"""Retry budget for outbound HTTP clients (local stand-in for payments SDK)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AttemptResult:
    ok: bool
    attempts: int
    exhausted: bool = False


@dataclass
class RetryBudget:
    """Caps retries for a logical operation.

    ``max_attempts`` includes the first try. Each failed call should consume one
    attempt; when the budget is exhausted further calls must fail fast without
    retrying forever.
    """

    max_attempts: int = 3
    _spent: dict[str, int] = field(default_factory=dict)

    def run(self, op_id: str, *, succeed_on_attempt: int | None = None) -> AttemptResult:
        """Simulate an operation that fails until ``succeed_on_attempt`` (1-based).

        When ``succeed_on_attempt`` is set, retries within this call until success
        or the budget is exhausted. When unset, consumes a single failed attempt.
        """
        spent = self._spent.get(op_id, 0)
        if spent >= self.max_attempts:
            return AttemptResult(ok=False, attempts=spent, exhausted=True)

        while spent < self.max_attempts:
            attempt = spent + 1
            if succeed_on_attempt is not None and attempt >= succeed_on_attempt:
                self._spent[op_id] = 0
                return AttemptResult(ok=True, attempts=attempt, exhausted=False)

            spent = attempt
            self._spent[op_id] = spent

            if succeed_on_attempt is None:
                exhausted = spent >= self.max_attempts
                return AttemptResult(ok=False, attempts=attempt, exhausted=exhausted)

        return AttemptResult(ok=False, attempts=spent, exhausted=True)

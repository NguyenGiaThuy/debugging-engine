"""Regression tests for outbound retry budget."""

from __future__ import annotations

from budget import RetryBudget


def test_succeeds_within_budget() -> None:
    rb = RetryBudget(max_attempts=3)
    # Remote recovers on 2nd attempt.
    assert rb.run("pay-1", succeed_on_attempt=2).ok is True


def test_exhausts_and_stops() -> None:
    """After max_attempts failures, further runs must report exhausted."""
    rb = RetryBudget(max_attempts=3)
    r1 = rb.run("pay-2", succeed_on_attempt=None)
    r2 = rb.run("pay-2", succeed_on_attempt=None)
    r3 = rb.run("pay-2", succeed_on_attempt=None)
    assert r1.ok is False and r2.ok is False and r3.ok is False
    assert r3.exhausted is True
    # Next call must fail fast with exhausted (no infinite retry loop).
    r4 = rb.run("pay-2", succeed_on_attempt=None)
    assert r4.exhausted is True
    assert r4.attempts <= 3


def test_ops_are_isolated() -> None:
    rb = RetryBudget(max_attempts=1)
    assert rb.run("a", succeed_on_attempt=None).exhausted is True
    assert rb.run("b", succeed_on_attempt=1).ok is True

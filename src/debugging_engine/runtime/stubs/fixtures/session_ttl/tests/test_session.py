"""Tests for SessionStore TTL / activity refresh behavior."""

from __future__ import annotations

from session import SessionStore


def test_fresh_session_is_active() -> None:
    store = SessionStore(ttl_seconds=10.0)
    store.create("s1", "alice", now=100.0)
    assert store.is_active("s1", now=105.0) is True


def test_untouched_session_expires() -> None:
    store = SessionStore(ttl_seconds=10.0)
    store.create("s1", "alice", now=100.0)
    assert store.is_active("s1", now=111.0) is False


def test_touch_extends_session_lifetime() -> None:
    """A session touched near the end of its TTL must remain active."""
    store = SessionStore(ttl_seconds=10.0)
    store.create("s1", "bob", now=100.0)
    # Client keeps the session alive with activity at t=108.
    assert store.touch("s1", now=108.0) is not None
    # At t=115 the creation-based window has ended, but last_seen was 108
    # so with a 10s TTL from last activity the session should still be active.
    assert store.is_active("s1", now=115.0) is True


def test_repeated_touch_keeps_long_lived_session() -> None:
    store = SessionStore(ttl_seconds=5.0)
    store.create("s1", "carol", now=0.0)
    for t in (4.0, 8.0, 12.0, 16.0):
        store.touch("s1", now=t)
        assert store.is_active("s1", now=t + 1.0) is True

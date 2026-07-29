"""Regression tests for webhook idempotent delivery."""

from __future__ import annotations

import pytest

from webhook import WebhookDispatcher


def test_successful_delivery_reaches_sink() -> None:
    disp = WebhookDispatcher()
    sink: list[dict] = []
    result = disp.deliver("evt-1", {"status": "paid", "amount": 10}, sink=sink)
    assert result.accepted is True
    assert result.deduped is False
    assert sink == [{"event_id": "evt-1", "body": {"status": "paid", "amount": 10}}]


def test_retry_after_transient_failure_delivers_once() -> None:
    disp = WebhookDispatcher()
    sink: list[dict] = []
    result = disp.deliver(
        "evt-2",
        {"status": "paid", "amount": 10, "_fail_once": True},
        sink=sink,
    )
    assert result.accepted is True
    assert result.attempts == 2
    assert len(sink) == 1


def test_corrected_payload_same_event_id_is_delivered() -> None:
    """Status corrections must not be swallowed by event-id-only dedupe."""
    disp = WebhookDispatcher()
    sink: list[dict] = []
    first = disp.deliver("evt-9", {"status": "pending", "amount": 10}, sink=sink)
    assert first.accepted is True
    # Merchant later corrects the event; same event_id, new body.
    second = disp.deliver("evt-9", {"status": "paid", "amount": 10}, sink=sink)
    assert second.accepted is True
    assert second.deduped is False
    assert [row["body"]["status"] for row in sink] == ["pending", "paid"]


def test_identical_retry_is_deduped() -> None:
    disp = WebhookDispatcher()
    sink: list[dict] = []
    payload = {"status": "paid", "amount": 5}
    disp.deliver("evt-3", payload, sink=sink)
    again = disp.deliver("evt-3", payload, sink=sink)
    assert again.deduped is True
    assert len(sink) == 1

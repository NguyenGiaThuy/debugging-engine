"""Webhook delivery helper — local stand-in for checkout notification fan-out."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


@dataclass
class DeliveryResult:
    accepted: bool
    attempts: int
    deduped: bool = False


@dataclass
class WebhookDispatcher:
    """Delivers signed webhooks with at-least-once retries and idempotency."""

    max_attempts: int = 3
    _seen: set[str] = field(default_factory=set)
    deliveries: list[dict] = field(default_factory=list)

    def _idempotency_key(self, event_id: str, payload: dict) -> str:
        # BUG: hashes only event_id. Retries with an updated payload (e.g. status
        # correction pending → paid) are silently dropped as duplicates.
        return hashlib.sha256(event_id.encode()).hexdigest()

    def deliver(self, event_id: str, payload: dict, *, sink: list[dict]) -> DeliveryResult:
        key = self._idempotency_key(event_id, payload)
        if key in self._seen:
            self.deliveries.append(
                {"event_id": event_id, "payload": payload, "deduped": True}
            )
            return DeliveryResult(accepted=True, attempts=0, deduped=True)

        attempts = 0
        last_error: Exception | None = None
        for _ in range(self.max_attempts):
            attempts += 1
            try:
                # Simulate flaky upstream: first attempt fails, later succeed.
                if attempts == 1 and payload.get("_fail_once"):
                    raise TimeoutError("upstream timeout")
                body = dict(payload)
                body.pop("_fail_once", None)
                sink.append({"event_id": event_id, "body": body})
                self._seen.add(key)
                self.deliveries.append(
                    {"event_id": event_id, "payload": body, "deduped": False}
                )
                return DeliveryResult(accepted=True, attempts=attempts, deduped=False)
            except TimeoutError as exc:
                last_error = exc
        raise RuntimeError(f"delivery failed after {attempts} attempts") from last_error

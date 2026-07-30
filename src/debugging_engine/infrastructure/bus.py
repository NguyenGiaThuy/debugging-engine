"""Event bus abstraction (Spec Part V) — sync JSONL default; async wrapper available."""

from __future__ import annotations

import asyncio
from typing import Protocol

from debugging_engine.domain.models import DomainEvent
from debugging_engine.infrastructure.store import ProjectionEngine


class EventBus(Protocol):
    """Append-only publication of domain events for a case."""

    def publish(self, events: list[DomainEvent]) -> None: ...


class SyncJsonlEventBus:
    """Default bus: validates and appends through ProjectionEngine (sync JSONL + lock)."""

    def __init__(self, engine: ProjectionEngine) -> None:
        self.engine = engine

    def publish(self, events: list[DomainEvent]) -> None:
        self.engine.append_many(events)


class AsyncQueueEventBus:
    """Async-capable bus: enqueues events and drains into the sync JSONL store.

    Spec Part V describes an async Event Bus; this wrapper preserves at-least-once
    append semantics while allowing producers to await publish without blocking the
    caller thread on flock I/O when used from asyncio tasks.
    """

    def __init__(self, engine: ProjectionEngine) -> None:
        self.engine = engine
        self._queue: asyncio.Queue[list[DomainEvent]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None

    def publish(self, events: list[DomainEvent]) -> None:
        # Sync path used by CaseService today.
        self.engine.append_many(events)

    async def publish_async(self, events: list[DomainEvent]) -> None:
        await self._queue.put(list(events))
        await self._ensure_worker()
        # Wait until queue drains this batch (simple barrier via empty check after join).
        await self._queue.join()

    async def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            batch = await self._queue.get()
            try:
                await asyncio.to_thread(self.engine.append_many, batch)
            finally:
                self._queue.task_done()

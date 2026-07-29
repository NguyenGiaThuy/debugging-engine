"""Stable public framework API (ADR 0005)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from debugging_engine.application.judge import Task
from debugging_engine.application.metrics import CaseMetrics, compute_case_metrics
from debugging_engine.application.service import CaseService
from debugging_engine.domain.models import DomainEvent
from debugging_engine.policies import DefaultSchedulingPolicy, SchedulingPolicy


class Engine:
    """Owns repository/store paths and scheduling policy."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        store_root: str | Path | None = None,
        policy: SchedulingPolicy | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.store_root = Path(store_root).resolve() if store_root else None
        self.policy = policy or DefaultSchedulingPolicy()
        self._service = CaseService(
            self.repo_root,
            store_root=self.store_root,
            policy=self.policy,
        )

    @property
    def service(self) -> CaseService:
        """Access underlying service (unstable; prefer Case methods)."""
        return self._service


class Case:
    """Bound investigation handle."""

    def __init__(self, engine: Engine, case_id: str) -> None:
        self.engine = engine
        self.case_id = case_id

    @classmethod
    def open(cls, engine: Engine, issue_path: str | Path) -> Case:
        """Create a Case + Unknown from an issue markdown file."""
        path = Path(issue_path)
        if not path.is_absolute():
            path = engine.repo_root / path
        case_id, _events = engine.service.open_issue(path)
        return cls(engine, case_id)

    @classmethod
    def load(cls, engine: Engine, case_id: str) -> Case:
        """Attach to an existing case id."""
        if engine.service.engine.project(case_id) is None:
            raise KeyError(case_id)
        return cls(engine, case_id)

    def next(self) -> Task:
        """Judge schedule — return next Task handoff."""
        return self.engine.service.next_task_model(self.case_id)

    def submit(self, events: Sequence[DomainEvent] | DomainEvent) -> dict[str, Any]:
        """Append validated domain events."""
        if isinstance(events, DomainEvent):
            batch = [events]
        else:
            batch = list(events)
        for event in batch:
            if not event.case_id:
                event.case_id = self.case_id
            elif event.case_id != self.case_id:
                raise ValueError(f"event case_id {event.case_id} != {self.case_id}")
        return self.engine.service.submit(batch)

    def verify(self, experiment_id: str) -> dict[str, Any]:
        """Run Verification Spec and record Evidence."""
        return self.engine.service.verify(self.case_id, experiment_id)

    def query(self, q: str = "summary") -> dict[str, Any]:
        return self.engine.service.query(self.case_id, q)

    def status(self) -> dict[str, Any]:
        return self.engine.service.status(self.case_id)

    def log(self) -> list[dict[str, Any]]:
        return self.engine.service.log(self.case_id)

    def replay(self) -> dict[str, Any]:
        return self.engine.service.replay(self.case_id)

    def metrics(self) -> CaseMetrics:
        return compute_case_metrics(self.engine.service.store, self.case_id)

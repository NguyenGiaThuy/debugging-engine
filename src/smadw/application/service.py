from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from smadw.application.judge import schedule_next_task
from smadw.domain.models import AgentRole, DomainEvent, EventType, new_id
from smadw.domain.validation import ValidationError
from smadw.infrastructure.store import JsonlEventStore, ProjectionEngine, dump_case_summary, query_case
from smadw.infrastructure.verify import run_verification


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_store_root(repo_root: Path) -> Path:
    return repo_root / ".smadw" / "cases"


class CaseService:
    def __init__(self, repo_root: Path, store_root: Path | None = None) -> None:
        self.repo_root = repo_root
        self.store = JsonlEventStore(store_root or default_store_root(repo_root))
        self.engine = ProjectionEngine(self.store)

    def open_issue(self, issue_path: Path) -> tuple[str, list[DomainEvent]]:
        text = issue_path.read_text(encoding="utf-8")
        title = next(
            (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
            issue_path.stem,
        )
        case_id = new_id()
        unknown_id = new_id()
        events = [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.CASE_CREATED,
                timestamp=utc_now(),
                producer=AgentRole.SYSTEM,
                payload={
                    "title": title,
                    "issue_path": str(issue_path.as_posix()),
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.INVESTIGATION_ACTIVATED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={},
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.UNKNOWN_DISCOVERED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": unknown_id,
                    "title": title,
                    "description": text[:4000],
                    "priority": "HIGH",
                    "related_components": ["subject/"],
                },
            ),
        ]
        self.engine.append_many(events)
        return case_id, events

    def status(self, case_id: str) -> dict:
        state = self.engine.project(case_id)
        if state is None:
            raise KeyError(case_id)
        return dump_case_summary(state)

    def next_task(self, case_id: str) -> dict:
        state = self.engine.project(case_id)
        if state is None:
            raise KeyError(case_id)
        return schedule_next_task(state).model_dump(mode="json")

    def query(self, case_id: str, q: str) -> dict:
        state = self.engine.project(case_id)
        if state is None:
            raise KeyError(case_id)
        return query_case(state, q)

    def submit(self, events: list[DomainEvent]) -> dict:
        if not events:
            raise ValidationError("No events provided")
        state = self.engine.append_many(events)
        return dump_case_summary(state)

    def verify(self, case_id: str, experiment_id: str) -> dict:
        emitted = run_verification(self.engine, case_id, experiment_id, self.repo_root)
        state = self.engine.project(case_id)
        assert state is not None
        return {
            "emitted": [e.model_dump(mode="json") for e in emitted],
            "case": dump_case_summary(state),
        }

    def log(self, case_id: str) -> list[dict]:
        return [e.model_dump(mode="json") for e in self.store.load_events(case_id)]

    def replay(self, case_id: str) -> dict:
        state = self.engine.project(case_id)
        if state is None:
            raise KeyError(case_id)
        return dump_case_summary(state)

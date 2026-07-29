from __future__ import annotations

import json
from pathlib import Path

from smadw.domain.models import CaseState, DomainEvent
from smadw.domain.validation import ValidationError, apply_event


class JsonlEventStore:
    """Append-only JSONL event log per case."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def case_dir(self, case_id: str) -> Path:
        path = self.root / case_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def events_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "events.jsonl"

    def append(self, event: DomainEvent) -> None:
        path = self.events_path(event.case_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")

    def load_events(self, case_id: str) -> list[DomainEvent]:
        path = self.events_path(case_id)
        if not path.exists():
            return []
        events: list[DomainEvent] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                events.append(DomainEvent.model_validate_json(line))
        return events

    def list_case_ids(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and (p / "events.jsonl").exists())


class ProjectionEngine:
    """Materialize Case State from Event Log."""

    def __init__(self, store: JsonlEventStore) -> None:
        self.store = store

    def project(self, case_id: str) -> CaseState | None:
        events = self.store.load_events(case_id)
        if not events:
            return None
        state: CaseState | None = None
        for event in events:
            state = apply_event(state, event)
        return state

    def append_validated(self, event: DomainEvent) -> CaseState:
        state = self.project(event.case_id)
        try:
            new_state = apply_event(state, event)
        except ValidationError:
            raise
        self.store.append(event)
        return new_state

    def append_many(self, events: list[DomainEvent]) -> CaseState:
        state: CaseState | None = None
        if events:
            state = self.project(events[0].case_id)
        for event in events:
            state = apply_event(state, event)
            self.store.append(event)
        if state is None:
            raise ValidationError("No events to append")
        return state


def dump_case_summary(state: CaseState) -> dict:
    return {
        "case_id": state.case_id,
        "title": state.title,
        "status": state.status,
        "issue_path": state.issue_path,
        "revision": state.revision,
        "event_count": state.event_count,
        "unknowns": {k: v.model_dump() for k, v in state.unknowns.items()},
        "hypotheses": {k: v.model_dump() for k, v in state.hypotheses.items()},
        "experiments": {k: v.model_dump() for k, v in state.experiments.items()},
        "evidence": {k: v.model_dump() for k, v in state.evidence.items()},
        "interpretations": {k: v.model_dump() for k, v in state.interpretations.items()},
        "decision_state": state.decision_state,
    }


def query_case(state: CaseState, query: str) -> dict:
    q = query.strip().lower()
    if q in {"", "summary", "case"}:
        return dump_case_summary(state)
    if q.startswith("unknown"):
        return {"unknowns": {k: v.model_dump() for k, v in state.unknowns.items()}}
    if q.startswith("hypothes"):
        return {"hypotheses": {k: v.model_dump() for k, v in state.hypotheses.items()}}
    if q.startswith("experiment") or q == "open experiments":
        open_exps = {
            k: v.model_dump()
            for k, v in state.experiments.items()
            if v.status.value not in {"COMPLETED", "FAILED", "CANCELLED", "EXPIRED"}
        }
        return {"experiments": open_exps}
    if q.startswith("evidence"):
        return {"evidence": {k: v.model_dump() for k, v in state.evidence.items()}}
    if q.startswith("interpret"):
        return {"interpretations": {k: v.model_dump() for k, v in state.interpretations.items()}}
    if q.startswith("decision"):
        return {"decision_state": state.decision_state}
    return {"error": f"Unknown query: {query}", "hint": "summary|unknowns|hypotheses|experiments|evidence|interpretations|decisions"}

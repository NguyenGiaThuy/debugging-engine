from __future__ import annotations

from pathlib import Path

from debugging_engine.domain.models import CaseState, DomainEvent
from debugging_engine.domain.validation import ValidationError, apply_event


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

    def lock_path(self, case_id: str) -> Path:
        return self.case_dir(case_id) / "events.lock"

    def _with_case_lock(self, case_id: str):
        """Exclusive lock for writers on a case event log (best-effort cross-process)."""
        import fcntl

        class _Lock:
            def __init__(self, path: Path) -> None:
                self.path = path
                self._fh = None

            def __enter__(self):
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = self.path.open("a+", encoding="utf-8")
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                assert self._fh is not None
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                self._fh.close()
                self._fh = None

        return _Lock(self.lock_path(case_id))

    def append(self, event: DomainEvent) -> None:
        path = self.events_path(event.case_id)
        with self._with_case_lock(event.case_id):
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
        with self.store._with_case_lock(event.case_id):
            state = self.project(event.case_id)
            try:
                new_state = apply_event(state, event)
            except ValidationError:
                raise
            path = self.store.events_path(event.case_id)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(event.model_dump_json() + "\n")
            return new_state

    def append_many(self, events: list[DomainEvent]) -> CaseState:
        if not events:
            raise ValidationError("No events to append")
        case_id = events[0].case_id
        if any(e.case_id != case_id for e in events):
            raise ValidationError("append_many requires a single case_id")
        # Validate the full batch against an in-memory projection before any durable write.
        with self.store._with_case_lock(case_id):
            state = self.project(case_id)
            trial = state
            for event in events:
                trial = apply_event(trial, event)
            path = self.store.events_path(case_id)
            with path.open("a", encoding="utf-8") as fh:
                for event in events:
                    fh.write(event.model_dump_json() + "\n")
            assert trial is not None
            return trial


def dump_case_summary(state: CaseState) -> dict:
    """Projection-friendly summary (K8): counts + light views, not full dumps."""
    return {
        "case_id": state.case_id,
        "title": state.title,
        "status": state.status,
        "issue_path": state.issue_path,
        "revision": state.revision,
        "event_count": state.event_count,
        "counts": {
            "unknowns": len(state.unknowns),
            "hypotheses": len(state.hypotheses),
            "experiments": len(state.experiments),
            "evidence": len(state.evidence),
            "interpretations": len(state.interpretations),
        },
        "unknowns": [
            {
                "id": u.id,
                "title": u.title,
                "status": u.status,
                "parent_unknown": u.parent_unknown,
                "revision": u.revision,
            }
            for u in state.unknowns.values()
        ],
        "hypotheses": [
            {
                "id": h.id,
                "title": h.title,
                "status": h.status,
                "unknown_id": h.unknown_id,
                "revision": h.revision,
            }
            for h in state.hypotheses.values()
        ],
        "decision_state": {
            k: state.decision_state[k]
            for k in (
                "root_cause_hypothesis_id",
                "escalated",
                "escalation_reason",
                "adversary_challenged",
                "scheduling_cycles",
                "stall_cycles",
                "last_progress_revision",
                "last_task",
                "human_responses",
                "partial_resolution",
            )
            if k in state.decision_state
        },
    }


def dump_case_full(state: CaseState) -> dict:
    """Full Case State dump — prefer query('full') / status(full=True)."""
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
    if q in {"full", "all"}:
        return dump_case_full(state)
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
    return {
        "error": f"Unknown query: {query}",
        "hint": "summary|full|unknowns|hypotheses|experiments|evidence|interpretations|decisions",
    }

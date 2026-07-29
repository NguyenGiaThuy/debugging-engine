from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from debugging_engine.application.judge import Task
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.domain.validation import ValidationError
from debugging_engine.infrastructure.store import JsonlEventStore, ProjectionEngine, dump_case_summary, query_case
from debugging_engine.infrastructure.verify import run_verification
from debugging_engine.policies import DefaultSchedulingPolicy, SchedulingPolicy


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_store_root(repo_root: Path) -> Path:
    return repo_root / ".debugging-engine" / "cases"


PROGRESS_EVENT_TYPES = {
    EventType.UNKNOWN_DISCOVERED,
    EventType.UNKNOWN_RESOLVED,
    EventType.HYPOTHESIS_PROPOSED,
    EventType.HYPOTHESIS_PROMOTED,
    EventType.HYPOTHESIS_WEAKENED,
    EventType.HYPOTHESIS_SUSPENDED,
    EventType.HYPOTHESIS_REJECTED,
    EventType.EXPERIMENT_PROPOSED,
    EventType.EXPERIMENT_APPROVED,
    EventType.EXPERIMENT_COMPLETED,
    EventType.EVIDENCE_RECORDED,
    EventType.INTERPRETATION_SUBMITTED,
    EventType.ROOT_CAUSE_ACCEPTED,
    EventType.PATCH_APPLIED,
    EventType.VERIFICATION_FAILED,
}

# Bootstrap after open: Analyst may propose before the first explicit `next`.
_BOOTSTRAP_ALLOWED = [
    EventType.HYPOTHESIS_PROPOSED.value,
    EventType.EXPERIMENT_PROPOSED.value,
]


class CaseService:
    def __init__(
        self,
        repo_root: Path,
        store_root: Path | None = None,
        policy: SchedulingPolicy | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.store = JsonlEventStore(store_root or default_store_root(repo_root))
        self.engine = ProjectionEngine(self.store)
        self.policy: SchedulingPolicy = policy or DefaultSchedulingPolicy()

    def _meta_path(self, case_id: str) -> Path:
        return self.store.case_dir(case_id) / "scheduler_meta.json"

    def _read_meta(self, case_id: str) -> dict:
        path = self._meta_path(case_id)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_meta(self, case_id: str, meta: dict) -> None:
        path = self._meta_path(case_id)
        path.write_text(json.dumps(meta), encoding="utf-8")

    def _bump_cycles(self, case_id: str, *, progress: bool) -> None:
        """ADR 0003 — track scheduling cycles and stall counter (sidecar meta)."""
        meta = self._read_meta(case_id)
        meta["scheduling_cycles"] = int(meta.get("scheduling_cycles", 0)) + 1
        state = self.engine.project(case_id)
        if progress:
            meta["stall_cycles"] = 0
            if state is not None:
                meta["last_progress_revision"] = state.revision
        else:
            meta["stall_cycles"] = int(meta.get("stall_cycles", 0)) + 1
        self._write_meta(case_id, meta)

    def _persist_task(self, case_id: str, task: Task) -> None:
        meta = self._read_meta(case_id)
        meta["last_task"] = {
            "role": task.role.value if hasattr(task.role, "value") else str(task.role),
            "allowed_event_types": list(task.allowed_event_types),
            "done": bool(task.done),
            "objective": task.objective,
        }
        self._write_meta(case_id, meta)

    def _enforce_task_allowed(self, case_id: str, events: list[DomainEvent]) -> None:
        """Reject submits whose event types are outside the last Judge Task."""
        meta = self._read_meta(case_id)
        last = meta.get("last_task")
        if not last:
            raise ValidationError(
                "No Judge Task issued; call next before submit",
                {"case_id": case_id},
            )
        if last.get("done"):
            raise ValidationError(
                "Investigation Task is terminal; no further submit",
                {"case_id": case_id},
            )
        allowed = set(last.get("allowed_event_types") or [])
        if not allowed:
            raise ValidationError(
                "Current Task allows no events; call next or escalate",
                {"role": last.get("role")},
            )
        for event in events:
            if event.producer == AgentRole.SYSTEM:
                continue
            if event.event_type.value not in allowed:
                raise ValidationError(
                    "Event type not allowed by current Judge Task",
                    {
                        "event_type": event.event_type.value,
                        "role": last.get("role"),
                        "allowed_event_types": sorted(allowed),
                    },
                )

    def _state_with_meta(self, case_id: str):
        state = self.engine.project(case_id)
        if state is None:
            return None
        meta = self._read_meta(case_id)
        if not meta:
            return state
        merged = state.model_copy(deep=True)
        for k in ("scheduling_cycles", "stall_cycles", "last_progress_revision"):
            if k in meta:
                merged.decision_state[k] = meta[k]
        return merged

    def _merge_meta_into_summary(self, case_id: str, summary: dict) -> dict:
        meta = self._read_meta(case_id)
        summary.setdefault("decision_state", {}).update(
            {k: meta[k] for k in ("scheduling_cycles", "stall_cycles", "last_progress_revision") if k in meta}
        )
        if "last_task" in meta:
            summary.setdefault("decision_state", {})["last_task"] = meta["last_task"]
        return summary

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
                    "related_components": [],
                },
            ),
        ]
        self.engine.append_many(events)
        self._bump_cycles(case_id, progress=True)
        # Bootstrap Task so the first Analyst submit is allowed without an extra next.
        self._write_meta(
            case_id,
            {
                **self._read_meta(case_id),
                "last_task": {
                    "role": AgentRole.ANALYST.value,
                    "allowed_event_types": list(_BOOTSTRAP_ALLOWED),
                    "done": False,
                    "objective": "Propose hypotheses and experiments for open unknowns.",
                },
            },
        )
        return case_id, events

    def status(self, case_id: str) -> dict:
        state = self._state_with_meta(case_id)
        if state is None:
            raise KeyError(case_id)
        return dump_case_summary(state)

    def next_task(self, case_id: str) -> dict:
        state = self._state_with_meta(case_id)
        if state is None:
            raise KeyError(case_id)
        task = self.policy.schedule(state)
        if not task.done:
            self._bump_cycles(case_id, progress=False)
            state = self._state_with_meta(case_id)
            assert state is not None
            task = self.policy.schedule(state)
        self._persist_task(case_id, task)
        return task.model_dump(mode="json")

    def next_task_model(self, case_id: str) -> Task:
        """Same as next_task but returns a Task model."""
        data = self.next_task(case_id)
        return Task.model_validate(data)

    def query(self, case_id: str, q: str) -> dict:
        state = self._state_with_meta(case_id)
        if state is None:
            raise KeyError(case_id)
        return query_case(state, q)

    def submit(self, events: list[DomainEvent]) -> dict:
        if not events:
            raise ValidationError("No events provided")
        case_id = events[0].case_id
        self._enforce_task_allowed(case_id, events)
        state = self.engine.append_many(events)
        progress = any(e.event_type in PROGRESS_EVENT_TYPES for e in events)
        self._bump_cycles(case_id, progress=progress)
        return self._merge_meta_into_summary(case_id, dump_case_summary(state))

    def verify(self, case_id: str, experiment_id: str) -> dict:
        emitted = run_verification(self.engine, case_id, experiment_id, self.repo_root)
        self._bump_cycles(case_id, progress=True)
        # Verifier path bypasses submit; require a fresh Judge Task before further submits.
        meta = self._read_meta(case_id)
        meta["last_task"] = None
        self._write_meta(case_id, meta)
        state = self._state_with_meta(case_id)
        assert state is not None
        return {
            "emitted": [e.model_dump(mode="json") for e in emitted],
            "case": dump_case_summary(state),
        }

    def log(self, case_id: str) -> list[dict]:
        return [e.model_dump(mode="json") for e in self.store.load_events(case_id)]

    def replay(self, case_id: str) -> dict:
        state = self._state_with_meta(case_id)
        if state is None:
            raise KeyError(case_id)
        return dump_case_summary(state)

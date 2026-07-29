from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.service import CaseService
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.domain.validation import ValidationError, apply_event
from debugging_engine.infrastructure.store import JsonlEventStore, ProjectionEngine
from debugging_engine.runtime.stubs.demo import run_stub_investigation


def test_case_created_and_replay(tmp_path: Path):
    store = JsonlEventStore(tmp_path / "cases")
    engine = ProjectionEngine(store)
    case_id = new_id()
    events = [
        DomainEvent(
            case_id=case_id,
            event_type=EventType.CASE_CREATED,
            timestamp="2026-07-29T00:00:00Z",
            producer=AgentRole.SYSTEM,
            payload={"title": "t", "issue_path": "x.md"},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.UNKNOWN_DISCOVERED,
            timestamp="2026-07-29T00:00:01Z",
            producer=AgentRole.ANALYST,
            payload={"id": new_id(), "title": "Why?"},
        ),
    ]
    engine.append_many(events)
    state = engine.project(case_id)
    assert state is not None
    assert state.event_count == 2
    assert len(state.unknowns) == 1
    # replay identical
    again = engine.project(case_id)
    assert again is not None
    assert again.model_dump() == state.model_dump()


def test_hypothesis_requires_unknown(tmp_path: Path):
    case_id = new_id()
    state = apply_event(
        None,
        DomainEvent(
            case_id=case_id,
            event_type=EventType.CASE_CREATED,
            timestamp="2026-07-29T00:00:00Z",
            producer=AgentRole.SYSTEM,
            payload={"title": "t"},
        ),
    )
    with pytest.raises(ValidationError):
        apply_event(
            state,
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp="2026-07-29T00:00:01Z",
                producer=AgentRole.ANALYST,
                payload={
                    "id": new_id(),
                    "unknown_id": "missing",
                    "title": "h",
                    "explanation": "e",
                },
            ),
        )


def test_stub_demo_resolves(tmp_path: Path):
    from fixtures import cache_miss_workspace

    workspace, issue = cache_miss_workspace(tmp_path)
    svc = CaseService(workspace, store_root=tmp_path / "cases")
    result = run_stub_investigation(svc, issue)
    assert result["status"] == "RESOLVED"
    assert "root_cause_hypothesis_id" in result["decision_state"]
    replayed = svc.replay(result["case_id"])
    assert replayed["status"] == "RESOLVED"
    assert replayed["event_count"] == len(svc.log(result["case_id"]))

from __future__ import annotations

from pathlib import Path

import pytest

from smadw.application.service import CaseService
from smadw.domain.models import AgentRole, DomainEvent, EventType, new_id
from smadw.domain.validation import ValidationError, apply_event
from smadw.infrastructure.store import JsonlEventStore, ProjectionEngine
from smadw.runtime.stubs.demo import run_stub_investigation


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
    root = Path(__file__).resolve().parents[1]
    cache_path = root / "subject" / "cache.py"
    original = cache_path.read_text(encoding="utf-8")
    buggy = '''\
"""Tiny in-memory cache used as the SMADW investigation subject."""


def normalize_key(key: str) -> str:
    # BUG: unused on set path — get lowercases, set does not.
    return key.strip().lower()


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        # BUG: stores raw key without normalization
        self._store[key] = value

    def get(self, key: str) -> object | None:
        return self._store.get(key.lower())

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store
'''
    cache_path.write_text(buggy, encoding="utf-8")
    try:
        svc = CaseService(root, store_root=tmp_path / "cases")
        issue = root / "subject" / "issues" / "001-cache-miss.md"
        result = run_stub_investigation(svc, issue)
        assert result["status"] == "RESOLVED"
        assert "root_cause_hypothesis_id" in result["decision_state"]
        replayed = svc.replay(result["case_id"])
        assert replayed["status"] == "RESOLVED"
        assert replayed["event_count"] == len(svc.log(result["case_id"]))
    finally:
        cache_path.write_text(original, encoding="utf-8")

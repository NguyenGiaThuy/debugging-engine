from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.domain.validation import ValidationError


def test_append_many_is_atomic_on_validation_failure(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# t\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    before = len(svc.engine.project(case_id).hypotheses)  # type: ignore[union-attr]
    good = DomainEvent(
        case_id=case_id,
        event_type=EventType.HYPOTHESIS_PROPOSED,
        timestamp=utc_now(),
        producer=AgentRole.ANALYST,
        payload={
            "id": new_id(),
            "unknown_id": unk,
            "title": "good",
            "explanation": "e",
            "assumptions": [],
        },
    )
    bad = DomainEvent(
        case_id=case_id,
        event_type=EventType.HYPOTHESIS_PROPOSED,
        timestamp=utc_now(),
        producer=AgentRole.ANALYST,
        payload={
            "id": new_id(),
            "unknown_id": "missing",
            "title": "bad",
            "explanation": "e",
            "assumptions": [],
        },
    )
    with pytest.raises(ValidationError):
        svc.submit([good, bad])
    st2 = svc.engine.project(case_id)
    assert st2 is not None
    assert len(st2.hypotheses) == before


def test_case_lock_file_created_on_append(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# t\n", encoding="utf-8")
    store_root = tmp_path / "cases"
    svc = CaseService(repo_root=root, store_root=store_root)
    case_id, _ = svc.open_issue(root / "issue.md")
    lock = store_root / case_id / "events.lock"
    assert lock.exists()

"""Adversary re-engage + tighter RootCause / patch proposal gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.judge import schedule_next_task, unrebutted_supports_evidence_ids
from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.domain.validation import ValidationError


def _open(tmp_path: Path) -> tuple[CaseService, str]:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# bug\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    return svc, case_id


def test_experiment_proposed_rejects_escaping_patch_path(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    with pytest.raises(ValidationError, match="patch paths"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.HYPOTHESIS_PROPOSED,
                    timestamp=utc_now(),
                    producer=AgentRole.ANALYST,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": "h",
                        "explanation": "e",
                    },
                ),
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.EXPERIMENT_PROPOSED,
                    timestamp=utc_now(),
                    producer=AgentRole.ANALYST,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": "bad patch",
                        "information_gain": "HIGH",
                        "cost": "LOW",
                        "experiment_class": "intervention",
                        "verification_spec": {
                            "command": ["python", "-c", "print(1)"],
                            "expected_exit_code": 0,
                        },
                        "patch": {"../evil.py": "x=1\n"},
                    },
                ),
            ]
        )


def test_analyst_cannot_forge_adversary_producer(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    with pytest.raises(ValidationError, match="producer must match"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.HYPOTHESIS_PROPOSED,
                    timestamp=utc_now(),
                    producer=AgentRole.ADVERSARY,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": "forged",
                        "explanation": "e",
                    },
                )
            ]
        )


def test_adversary_reengages_after_unrebutted_supports(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, alt, eid = new_id(), new_id(), new_id()
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": hid,
                    "unknown_id": unk,
                    "title": "primary",
                    "explanation": "e",
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": eid,
                    "unknown_id": unk,
                    "title": "obs",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hid],
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                    },
                },
            ),
        ]
    )
    task = svc.next_task(case_id)
    assert task["role"] == AgentRole.ADVERSARY.value
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ADVERSARY,
                payload={
                    "id": alt,
                    "unknown_id": unk,
                    "title": "alt",
                    "explanation": "e",
                },
            )
        ]
    )
    task = svc.next_task(case_id)
    assert task["role"] == AgentRole.JUDGE.value
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_APPROVED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"experiment_id": eid, "authority": "Judge"},
            )
        ]
    )
    svc.verify(case_id, eid)
    st = svc.engine.project(case_id)
    assert st is not None
    evid = next(iter(st.evidence))
    svc.next_task(case_id)
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.INTERPRETATION_SUBMITTED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": new_id(),
                    "evidence_id": evid,
                    "hypothesis_id": hid,
                    "outcome": "SUPPORTS",
                    "rationale": "looks good",
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": new_id(),
                    "unknown_id": unk,
                    "title": "fix",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "experiment_class": "intervention",
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                    },
                    "patch": {"f.py": "x=1\n"},
                },
            ),
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert unrebutted_supports_evidence_ids(st) == [evid]
    task = schedule_next_task(st)
    assert task.role == AgentRole.ADVERSARY
    assert evid in task.projection["unrebutted_evidence_ids"]

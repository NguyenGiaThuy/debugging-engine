"""Regression tests for single-thread loop hardening (issues 001/005 + parent prune)."""

from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import (
    AgentRole,
    DomainEvent,
    EventType,
    ExperimentStatus,
    HypothesisStatus,
    new_id,
)
from debugging_engine.domain.validation import ValidationError
from debugging_engine.infrastructure.paths import resolve_under_root
from debugging_engine.infrastructure.verify import run_verification


def _open(tmp_path: Path) -> tuple[CaseService, str]:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# bug\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    return svc, case_id


def test_resolve_under_root_rejects_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(ValidationError, match=r"\.\.|absolute|escapes"):
        resolve_under_root(root, "../outside.txt", what="patch path")
    with pytest.raises(ValidationError, match="absolute|relative"):
        resolve_under_root(root, "/etc/passwd", what="patch path")
    assert resolve_under_root(root, "ok.py", what="patch path") == (root / "ok.py").resolve()


def test_verify_path_escape_fails_experiment(tmp_path: Path):
    """Escaping patch paths are rejected at ExperimentProposed (fail closed)."""
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, eid = new_id(), new_id()
    with pytest.raises(ValidationError, match="patch paths"):
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
                        "id": eid,
                        "unknown_id": unk,
                        "title": "evil patch",
                        "information_gain": "HIGH",
                        "cost": "LOW",
                        "affected_hypotheses": [hid],
                        "experiment_class": "intervention",
                        "verification_spec": {
                            "command": ["python", "-c", "print(1)"],
                            "expected_exit_code": 0,
                            "working_directory": ".",
                        },
                        "patch": {"../escape.txt": "pwned\n"},
                    },
                ),
            ]
        )
    assert not (tmp_path / "escape.txt").exists()


def _approve_after_adversary(svc: CaseService, case_id: str, eid: str) -> None:
    task = svc.next_task(case_id)
    assert task["role"] == AgentRole.ADVERSARY.value
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
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
                    "title": "alt",
                    "explanation": "e",
                    "objection_category": "Alternative Hypothesis",
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


def test_verify_cwd_escape_fails_experiment(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, eid = new_id(), new_id()
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
                    "id": eid,
                    "unknown_id": unk,
                    "title": "cwd escape",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hid],
                    "experiment_class": "observational",
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                        "working_directory": "..",
                    },
                },
            ),
        ]
    )
    _approve_after_adversary(svc, case_id, eid)
    emitted = run_verification(svc.engine, case_id, eid, svc.repo_root)
    assert any(e.event_type == EventType.VERIFICATION_FAILED for e in emitted)
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.experiments[eid].status == ExperimentStatus.FAILED


def test_verify_unexpected_exit_marks_failed_not_completed(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, eid = new_id(), new_id()
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
                    "id": eid,
                    "unknown_id": unk,
                    "title": "failing",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hid],
                    "experiment_class": "observational",
                    "verification_spec": {
                        "command": ["python", "-c", "raise SystemExit(1)"],
                        "expected_exit_code": 0,
                        "working_directory": ".",
                    },
                },
            ),
        ]
    )
    _approve_after_adversary(svc, case_id, eid)
    emitted = run_verification(svc.engine, case_id, eid, svc.repo_root)
    types = [e.event_type for e in emitted]
    assert EventType.EVIDENCE_RECORDED in types
    assert EventType.VERIFICATION_FAILED in types
    assert EventType.EXPERIMENT_COMPLETED not in types
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.experiments[eid].status == ExperimentStatus.FAILED


def test_root_cause_requires_evidence_and_judge(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid = new_id()
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
                    "title": "h",
                    "explanation": "e",
                },
            )
        ]
    )
    # Force a Judge-like Task that allows accept so we hit domain gates, not task binding.
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.JUDGE.value,
                "allowed_event_types": [EventType.ROOT_CAUSE_ACCEPTED.value],
                "done": False,
                "objective": "test",
            },
        },
    )
    with pytest.raises(ValidationError, match="authority Judge"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.ROOT_CAUSE_ACCEPTED,
                    timestamp=utc_now(),
                    producer=AgentRole.JUDGE,
                    payload={"hypothesis_id": hid, "rationale": "because"},
                )
            ]
        )
    with pytest.raises(ValidationError, match="supporting interpretation"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.ROOT_CAUSE_ACCEPTED,
                    timestamp=utc_now(),
                    producer=AgentRole.JUDGE,
                    payload={
                        "hypothesis_id": hid,
                        "rationale": "because",
                        "authority": "Judge",
                    },
                )
            ]
        )


def test_analyst_patch_applied_rejected(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    eid = new_id()
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
                    "id": eid,
                    "unknown_id": unk,
                    "title": "exp",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                    },
                },
            ),
        ]
    )
    # Domain gate: even if Task role matches producer, PatchApplied rejects Analyst.
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.ANALYST.value,
                "allowed_event_types": [EventType.PATCH_APPLIED.value],
                "done": False,
                "objective": "test",
            },
        },
    )
    with pytest.raises(ValidationError, match="Implementer"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.PATCH_APPLIED,
                    timestamp=utc_now(),
                    producer=AgentRole.ANALYST,
                    payload={"experiment_id": eid, "paths": ["f.py"]},
                )
            ]
        )


def test_submit_rejects_disallowed_event_type(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    eid = new_id()
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
                    "id": eid,
                    "unknown_id": unk,
                    "title": "exp",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                    },
                },
            ),
        ]
    )
    with pytest.raises(ValidationError, match="not allowed"):
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


def test_hypothesis_parent_reject_cascades(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    parent = new_id()
    child = new_id()
    grandchild = new_id()
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": parent,
                    "unknown_id": unk,
                    "title": "parent",
                    "explanation": "e",
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": child,
                    "unknown_id": unk,
                    "title": "child",
                    "explanation": "e",
                    "parent_id": parent,
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": grandchild,
                    "unknown_id": unk,
                    "title": "grandchild",
                    "explanation": "e",
                    "parent_id": child,
                },
            ),
        ]
    )
    # Allow reject under a Judge Task for the test.
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.JUDGE.value,
                "allowed_event_types": [EventType.HYPOTHESIS_REJECTED.value],
                "done": False,
                "objective": "prune",
            },
        },
    )
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_REJECTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"hypothesis_id": parent, "reason": "disproved"},
            )
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.hypotheses[parent].status == HypothesisStatus.REJECTED
    assert st.hypotheses[child].status == HypothesisStatus.REJECTED
    assert st.hypotheses[grandchild].status == HypothesisStatus.REJECTED

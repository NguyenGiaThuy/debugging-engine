"""Tests for K1–K8 kernel gaps."""

from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, ObjectionCategory, new_id
from debugging_engine.domain.validation import ValidationError
from debugging_engine.infrastructure.bus import AsyncQueueEventBus, SyncJsonlEventBus


def _open(tmp_path: Path) -> tuple[CaseService, str, str]:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# bug\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    unk = next(iter(svc.engine.project(case_id).unknowns))  # type: ignore[union-attr]
    return svc, case_id, unk


def test_k1_rich_verification_thresholds(tmp_path: Path):
    svc, case_id, unk = _open(tmp_path)
    hid, eid = new_id(), new_id()
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={"id": hid, "unknown_id": unk, "title": "h", "explanation": "e"},
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": eid,
                    "unknown_id": unk,
                    "title": "metrics",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "verification_spec": {
                        "command": ["python", "-c", "print('latency_ms=12')"],
                        "expected_exit_code": 0,
                        "metrics": ["latency_ms"],
                        "thresholds": {"latency_ms": 10.0},
                        "baselines": {"latency_ms": 5.0},
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
                    "id": new_id(),
                    "unknown_id": unk,
                    "title": "alt",
                    "explanation": "e",
                    "objection_category": ObjectionCategory.ALTERNATIVE_HYPOTHESIS.value,
                },
            )
        ]
    )
    task = svc.next_task(case_id)
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
    out = svc.verify(case_id, eid)
    st = svc.engine.project(case_id)
    assert st is not None
    evid = next(iter(st.evidence.values()))
    assert evid.attributes.get("threshold_ok") is False
    assert st.experiments[eid].status.value == "FAILED"


def test_k2_adversary_requires_objection_category(tmp_path: Path):
    svc, case_id, unk = _open(tmp_path)
    hid, eid = new_id(), new_id()
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={"id": hid, "unknown_id": unk, "title": "a", "explanation": "e"},
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": eid,
                    "unknown_id": unk,
                    "title": "e",
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
    svc.next_task(case_id)
    with pytest.raises(ValidationError, match="objection_category"):
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
                    },
                )
            ]
        )


def test_k3_k4_unknown_hierarchy_and_partial(tmp_path: Path):
    svc, case_id, parent = _open(tmp_path)
    child = new_id()
    # Bootstrap is Analyst — propose is fine; need next for unknown events?
    # UnknownDiscovered only at open; submit child under Analyst bootstrap — not allowed.
    # Use Judge after we get a task that allows it, or write meta.
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.ANALYST.value,
                "allowed_event_types": [
                    EventType.UNKNOWN_DISCOVERED.value,
                    EventType.UNKNOWN_PARTIALLY_RESOLVED.value,
                ],
                "done": False,
                "objective": "test",
            },
        },
    )
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.UNKNOWN_DISCOVERED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": child,
                    "title": "child unknown",
                    "description": "nested",
                    "parent_unknown": parent,
                },
            )
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.unknowns[child].parent_unknown == parent
    assert child in st.unknowns[parent].child_unknowns
    assert st.unknowns[parent].revision >= 2
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.UNKNOWN_PARTIALLY_RESOLVED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={"unknown_id": child, "rationale": "one facet fixed"},
            )
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.unknowns[child].status.value == "PARTIALLY_RESOLVED"


def test_k5_object_revision_bumps(tmp_path: Path):
    svc, case_id, unk = _open(tmp_path)
    hid = new_id()
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={"id": hid, "unknown_id": unk, "title": "h", "explanation": "e"},
            )
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.hypotheses[hid].revision == 1
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.JUDGE.value,
                "allowed_event_types": [EventType.HYPOTHESIS_SUSPENDED.value],
                "done": False,
                "objective": "t",
            },
        },
    )
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_SUSPENDED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"hypothesis_id": hid, "reason": "parked"},
            )
        ]
    )
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.hypotheses[hid].revision == 2


def test_k6_event_bus_sync_and_async(tmp_path: Path):
    svc, case_id, unk = _open(tmp_path)
    bus = SyncJsonlEventBus(svc.engine)
    assert hasattr(bus, "publish")
    async_bus = AsyncQueueEventBus(svc.engine)
    assert hasattr(async_bus, "publish_async")


def test_k8_status_summary_vs_full(tmp_path: Path):
    svc, case_id, _ = _open(tmp_path)
    summary = svc.status(case_id)
    assert "counts" in summary
    assert isinstance(summary["unknowns"], list)
    full = svc.status(case_id, full=True)
    assert isinstance(full["unknowns"], dict)
    assert "evidence" in full

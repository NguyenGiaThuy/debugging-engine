"""M1–M3: investigation modes, FixAccepted, org/human production gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.judge import schedule_next_task
from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import (
    AgentRole,
    DomainEvent,
    EventType,
    InvestigationMode,
    new_id,
)
from debugging_engine.domain.validation import ValidationError


def _open(
    tmp_path: Path,
    *,
    mode: InvestigationMode | str = InvestigationMode.INCIDENT,
) -> tuple[CaseService, str]:
    root = tmp_path / "ws"
    root.mkdir(exist_ok=True)
    (root / "issue.md").write_text("# bug\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md", mode=mode)
    return svc, case_id


def _force_task(svc: CaseService, case_id: str, role: AgentRole, allowed: list[str]) -> None:
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": role.value,
                "allowed_event_types": allowed,
                "done": False,
                "objective": "test",
            },
        },
    )


def _seed_observational_supports(svc: CaseService, case_id: str) -> str:
    """Minimal path to a supported hypothesis with passed observational evidence."""
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, eid, evid, iid = new_id(), new_id(), new_id(), new_id()
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
    # Skip dialectic/approve/verify ceremony: inject completed experiment + evidence.
    for event in [
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_APPROVED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": eid, "authority": "Judge"},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_SCHEDULED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": eid},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_STARTED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": eid},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_COMPLETED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": eid},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EVIDENCE_RECORDED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={
                "id": evid,
                "experiment_id": eid,
                "observation": "ok",
                "provenance": "test",
                "attributes": {"passed": True, "exit_code": 0},
            },
        ),
    ]:
        svc.engine.append_validated(event)

    _force_task(
        svc,
        case_id,
        AgentRole.ANALYST,
        [EventType.INTERPRETATION_SUBMITTED.value, EventType.HYPOTHESIS_REJECTED.value],
    )
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.INTERPRETATION_SUBMITTED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": iid,
                    "evidence_id": evid,
                    "hypothesis_id": hid,
                    "outcome": "SUPPORTS",
                    "rationale": "matches",
                },
            )
        ]
    )
    return hid


def test_open_persists_mode(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="production")
    st = svc.status(case_id)
    assert st["mode"] == "production"
    assert st["accepted_root_cause_id"] is None


def test_investigate_rejects_intervention(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="investigate")
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    with pytest.raises(ValidationError, match="investigate mode forbids intervention"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.EXPERIMENT_PROPOSED,
                    timestamp=utc_now(),
                    producer=AgentRole.ANALYST,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": "fix",
                        "experiment_class": "intervention",
                        "patch": {"a.py": "x"},
                    },
                )
            ]
        )


def test_investigate_rca_resolves(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="investigate")
    hid = _seed_observational_supports(svc, case_id)
    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.ROOT_CAUSE_ACCEPTED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.ROOT_CAUSE_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={
                    "hypothesis_id": hid,
                    "rationale": "observed",
                    "authority": "Judge",
                },
            )
        ]
    )
    st = svc.status(case_id)
    assert st["status"] == "RESOLVED"
    assert st["accepted_root_cause_id"] == hid


def test_incident_needs_fix_accepted_when_intervention_exists(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="incident")
    hid = _seed_observational_supports(svc, case_id)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    fix_id = new_id()
    _force_task(svc, case_id, AgentRole.ANALYST, [EventType.EXPERIMENT_PROPOSED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": fix_id,
                    "unknown_id": unk,
                    "title": "patch",
                    "experiment_class": "intervention",
                    "cost": "LOW",
                    "information_gain": "HIGH",
                    "patch": {"bug.py": "fixed\n"},
                    "verification_spec": {
                        "command": ["python", "-c", "print(1)"],
                        "expected_exit_code": 0,
                    },
                },
            )
        ]
    )
    # Complete intervention with passed evidence via direct append.
    evid = new_id()
    for event in [
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_APPROVED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": fix_id, "authority": "Judge"},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_SCHEDULED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_STARTED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_COMPLETED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EVIDENCE_RECORDED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={
                "id": evid,
                "experiment_id": fix_id,
                "observation": "fixed",
                "provenance": "test",
                "attributes": {"passed": True, "exit_code": 0},
            },
        ),
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
                "rationale": "fix works",
            },
        ),
    ]:
        svc.engine.append_validated(event)

    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.ROOT_CAUSE_ACCEPTED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.ROOT_CAUSE_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={
                    "hypothesis_id": hid,
                    "rationale": "cause known",
                    "authority": "Judge",
                },
            )
        ]
    )
    st = svc.status(case_id)
    assert st["status"] == "ACTIVE"
    assert st["accepted_root_cause_id"] == hid

    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.FIX_ACCEPTED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.FIX_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"rationale": "fix verified", "authority": "Judge"},
            )
        ]
    )
    assert svc.status(case_id)["status"] == "RESOLVED"


def test_production_blocks_high_approve_without_human(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="production")
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
                    "title": "risky",
                    "experiment_class": "intervention",
                    "cost": "HIGH",
                    "information_gain": "HIGH",
                    "patch": {"x.py": "y"},
                },
            ),
        ]
    )
    # Mark adversary challenged so approve can be attempted.
    st2 = svc.engine.project(case_id)
    assert st2 is not None
    st2.decision_state["adversary_challenged"] = True
    # Direct validation of ExperimentApproved
    from debugging_engine.domain.validation import validate_event

    with pytest.raises(ValidationError, match="Human approve"):
        validate_event(
            svc.engine.project(case_id),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_APPROVED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"experiment_id": eid, "authority": "Judge"},
            ),
        )

    _force_task(svc, case_id, AgentRole.HUMAN, [EventType.HUMAN_RESPONSE_RECEIVED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HUMAN_RESPONSE_RECEIVED,
                timestamp=utc_now(),
                producer=AgentRole.HUMAN,
                payload={
                    "message": "ok to ship",
                    "approval_for": eid,
                    "decision": "approve",
                },
            )
        ]
    )
    validate_event(
        svc.engine.project(case_id),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_APPROVED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": eid, "authority": "Judge"},
        ),
    )


def test_human_approve_cli_helper(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="production")
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
                    "title": "risky",
                    "experiment_class": "intervention",
                    "cost": "HIGH",
                    "information_gain": "HIGH",
                    "patch": {"x.py": "y"},
                },
            ),
        ]
    )
    out = svc.human_approve_intervention(case_id, eid, decision="approve", message="user ok")
    assert out["decision_state"]["intervention_approvals"][eid] == "approve"


def test_production_fix_needs_org_approval(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="production")
    hid = _seed_observational_supports(svc, case_id)
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    fix_id = new_id()
    evid = new_id()
    # Propose LOW-cost intervention (no Human approve gate) and complete it.
    _force_task(svc, case_id, AgentRole.ANALYST, [EventType.EXPERIMENT_PROPOSED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=utc_now(),
                producer=AgentRole.ANALYST,
                payload={
                    "id": fix_id,
                    "unknown_id": unk,
                    "title": "patch",
                    "experiment_class": "intervention",
                    "cost": "LOW",
                    "information_gain": "HIGH",
                    "patch": {"bug.py": "fixed\n"},
                },
            )
        ]
    )
    for event in [
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_APPROVED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": fix_id, "authority": "Judge"},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_SCHEDULED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_STARTED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_COMPLETED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={"experiment_id": fix_id},
        ),
        DomainEvent(
            case_id=case_id,
            event_type=EventType.EVIDENCE_RECORDED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            payload={
                "id": evid,
                "experiment_id": fix_id,
                "observation": "fixed",
                "provenance": "test",
                "attributes": {"passed": True, "exit_code": 0},
            },
        ),
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
                "rationale": "fix works",
            },
        ),
    ]:
        svc.engine.append_validated(event)

    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.ROOT_CAUSE_ACCEPTED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.ROOT_CAUSE_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={
                    "hypothesis_id": hid,
                    "rationale": "cause",
                    "authority": "Judge",
                },
            )
        ]
    )
    assert svc.status(case_id)["status"] == "ACTIVE"

    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.FIX_ACCEPTED.value])
    with pytest.raises(ValidationError, match="OrgApprovalReceived"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.FIX_ACCEPTED,
                    timestamp=utc_now(),
                    producer=AgentRole.JUDGE,
                    payload={"rationale": "fix", "authority": "Judge"},
                )
            ]
        )

    task = schedule_next_task(svc.engine.project(case_id))  # type: ignore[arg-type]
    assert task.role == AgentRole.HUMAN
    assert EventType.ORG_APPROVAL_RECEIVED.value in task.allowed_event_types

    _force_task(svc, case_id, AgentRole.HUMAN, [EventType.ORG_APPROVAL_RECEIVED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.ORG_APPROVAL_RECEIVED,
                timestamp=utc_now(),
                producer=AgentRole.HUMAN,
                payload={"approved": True, "rationale": "CAB signed off"},
            )
        ]
    )
    _force_task(svc, case_id, AgentRole.JUDGE, [EventType.FIX_ACCEPTED.value])
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.FIX_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={"rationale": "fix", "authority": "Judge"},
            )
        ]
    )
    assert svc.status(case_id)["status"] == "RESOLVED"
    assert svc.status(case_id)["decision_state"].get("org_approved") is True


def test_judge_schedules_human_for_risky_production_approve(tmp_path: Path):
    svc, case_id = _open(tmp_path, mode="production")
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
                    "title": "risky",
                    "experiment_class": "intervention",
                    "cost": "CRITICAL",
                    "information_gain": "HIGH",
                    "patch": {"x.py": "y"},
                },
            ),
        ]
    )
    # Satisfy dialectic: adversary challenge
    svc.next_task(case_id)
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
    task = schedule_next_task(svc.engine.project(case_id))  # type: ignore[arg-type]
    assert task.role == AgentRole.HUMAN
    assert EventType.HUMAN_RESPONSE_RECEIVED.value in task.allowed_event_types

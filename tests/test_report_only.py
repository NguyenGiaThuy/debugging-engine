"""Report-only accept path (investigate skill) vs intervention (incident skill)."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.application.judge import schedule_next_task
from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id


def _open(tmp_path: Path) -> tuple[CaseService, str]:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# bug\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    return svc, case_id


def _observe_and_supports(svc: CaseService, case_id: str) -> tuple[str, str]:
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
                    "id": new_id(),
                    "unknown_id": unk,
                    "title": "alt",
                    "explanation": "e",
                    "objection_category": "Alternative Hypothesis",
                },
            )
        ]
    )
    # Reject competitor so RootCauseAccepted can pass later.
    alt = [h for h in svc.engine.project(case_id).hypotheses.values() if h.id != hid][0]  # type: ignore[union-attr]
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
                    "rationale": "matches",
                },
            )
        ]
    )
    # Adversary rebuttal (suspend competitor is allowed on this Task)
    task = svc.next_task(case_id)
    assert task["role"] == AgentRole.ADVERSARY.value
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.INTERPRETATION_SUBMITTED,
                timestamp=utc_now(),
                producer=AgentRole.ADVERSARY,
                payload={
                    "id": new_id(),
                    "evidence_id": evid,
                    "hypothesis_id": hid,
                    "outcome": "INCONCLUSIVE",
                    "objection_category": "Incomplete Explanation",
                    "rationale": "conceded strongest lead",
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_SUSPENDED,
                timestamp=utc_now(),
                producer=AgentRole.ADVERSARY,
                payload={"hypothesis_id": alt.id, "reason": "weakened by observation"},
            ),
        ]
    )
    return hid, evid


def test_report_only_schedules_judge_accept_without_intervention(tmp_path: Path):
    svc, case_id = _open(tmp_path)
    hid, _ = _observe_and_supports(svc, case_id)
    task = schedule_next_task(svc.engine.project(case_id))  # type: ignore[arg-type]
    assert task.role == AgentRole.JUDGE
    assert task.projection.get("report_only") is True
    assert EventType.ROOT_CAUSE_ACCEPTED.value in task.allowed_event_types
    svc._write_meta(
        case_id,
        {
            **svc._read_meta(case_id),
            "last_task": {
                "role": AgentRole.JUDGE.value,
                "allowed_event_types": list(task.allowed_event_types),
                "done": False,
                "objective": task.objective,
            },
        },
    )
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.ROOT_CAUSE_ACCEPTED,
                timestamp=utc_now(),
                producer=AgentRole.JUDGE,
                payload={
                    "hypothesis_id": hid,
                    "rationale": "observational evidence sufficient",
                    "authority": "Judge",
                },
            )
        ]
    )
    st = svc.status(case_id)
    assert st["status"] == "RESOLVED"

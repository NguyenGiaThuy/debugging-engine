from __future__ import annotations

from pathlib import Path

from debugging_engine.application.judge import schedule_next_task
from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import (
    AgentRole,
    DomainEvent,
    EventType,
    HypothesisStatus,
    new_id,
)


def _submit_hyp_and_exp(
    svc: CaseService,
    case_id: str,
    *,
    with_patch: bool = False,
) -> tuple[str, str]:
    st = svc.engine.project(case_id)
    assert st is not None
    unk = next(iter(st.unknowns))
    hid, eid = new_id(), new_id()
    ts = utc_now()
    payload = {
        "id": eid,
        "unknown_id": unk,
        "title": "exp",
        "information_gain": "HIGH",
        "cost": "LOW",
        "affected_hypotheses": [hid],
        "expected_observations": ["ok"],
        "experiment_class": "intervention" if with_patch else "observational",
        "verification_spec": {
            "command": ["python", "-c", "print(1)"],
            "expected_exit_code": 0,
            "working_directory": ".",
        },
    }
    if with_patch:
        payload["patch"] = {"f.py": "x=2\n"}
        (svc.repo_root / "f.py").write_text("x=1\n", encoding="utf-8")
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp=ts,
                producer=AgentRole.ANALYST,
                payload={
                    "id": hid,
                    "unknown_id": unk,
                    "title": "h",
                    "explanation": "e",
                    "assumptions": [],
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.EXPERIMENT_PROPOSED,
                timestamp=ts,
                producer=AgentRole.ANALYST,
                payload=payload,
            ),
        ]
    )
    return hid, eid


def test_single_hyp_approved_experiment_schedules_verifier(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# t\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    _, eid = _submit_hyp_and_exp(svc, case_id)
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
    task = schedule_next_task(svc.engine.project(case_id))  # type: ignore[arg-type]
    assert task.role == AgentRole.VERIFIER


def test_intervention_patch_schedules_implementer(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# t\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    _, eid = _submit_hyp_and_exp(svc, case_id, with_patch=True)
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
    task = schedule_next_task(svc.engine.project(case_id))  # type: ignore[arg-type]
    assert task.role == AgentRole.IMPLEMENTER
    assert task.projection["experiment"]["has_patch"] is True


def test_supports_promotes_proposed_hypothesis(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    (root / "issue.md").write_text("# t\n", encoding="utf-8")
    svc = CaseService(repo_root=root, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(root / "issue.md")
    hid, eid = _submit_hyp_and_exp(svc, case_id)
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
    st = svc.engine.project(case_id)
    assert st is not None
    assert st.hypotheses[hid].status == HypothesisStatus.PLAUSIBLE
    task = schedule_next_task(st)
    assert task.role == AgentRole.ANALYST
    assert "intervention" in task.objective.lower()

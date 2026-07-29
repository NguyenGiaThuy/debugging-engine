from __future__ import annotations

from pathlib import Path

from debugging_engine import (
    Case,
    DomainEvent,
    Engine,
    EventType,
    SchedulingPolicy,
    Task,
    ValidationError,
    __version__,
    schedule_next_task,
)
from debugging_engine.domain.models import AgentRole, CaseState, new_id
from debugging_engine.policies import DefaultSchedulingPolicy


def test_public_exports():
    assert __version__ == "0.7.0"
    assert callable(schedule_next_task)
    assert issubclass(DefaultSchedulingPolicy, object)


def test_case_open_next_via_api(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    engine = Engine(repo_root=root, store_root=tmp_path / "cases")
    case = Case.open(engine, root / "subject" / "issues" / "001-cache-miss.md")
    task = case.next()
    assert isinstance(task, Task)
    assert task.case_id == case.case_id
    assert task.role == AgentRole.ANALYST
    status = case.status()
    assert status["case_id"] == case.case_id
    assert "unknowns" in status
    loaded = Case.load(engine, case.case_id)
    assert loaded.case_id == case.case_id


def test_custom_scheduling_policy(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]

    class EscalateHint:
        def schedule(self, state: CaseState) -> Task:
            return Task(
                case_id=state.case_id,
                role=AgentRole.JUDGE,
                objective="custom-policy",
                allowed_event_types=[EventType.INVESTIGATION_ESCALATED.value],
                projection={"custom": True},
                done=False,
            )

    assert isinstance(EscalateHint(), SchedulingPolicy)
    engine = Engine(repo_root=root, store_root=tmp_path / "cases", policy=EscalateHint())
    case = Case.open(engine, root / "subject" / "issues" / "001-cache-miss.md")
    task = case.next()
    assert task.objective == "custom-policy"
    assert task.projection.get("custom") is True


def test_submit_and_query_via_api(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    engine = Engine(repo_root=root, store_root=tmp_path / "cases")
    case = Case.open(engine, root / "subject" / "issues" / "001-cache-miss.md")
    unk = next(iter(case.status()["unknowns"]))
    case.submit(
        DomainEvent(
            case_id=case.case_id,
            event_type=EventType.HYPOTHESIS_PROPOSED,
            timestamp="2026-07-29T00:00:00Z",
            producer=AgentRole.ANALYST,
            payload={
                "id": new_id(),
                "unknown_id": unk,
                "title": "api hyp",
                "explanation": "from public API",
            },
        )
    )
    hyps = case.query("hypotheses")
    assert len(hyps["hypotheses"]) == 1
    metrics = case.metrics()
    assert metrics.hypotheses == 1
    assert metrics.case_id == case.case_id


def test_validation_error_surfaces(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    engine = Engine(repo_root=root, store_root=tmp_path / "cases")
    case = Case.open(engine, root / "subject" / "issues" / "001-cache-miss.md")
    try:
        case.submit([])
        assert False, "expected ValidationError"
    except ValidationError:
        pass

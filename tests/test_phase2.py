from __future__ import annotations

from pathlib import Path

import pytest

from debugging_engine.application.judge import schedule_next_task
from debugging_engine.application.service import CaseService
from debugging_engine.domain.models import (
    AgentRole,
    DomainEvent,
    EventType,
    HypothesisStatus,
    Unknown,
    UnknownStatus,
    CaseState,
    Hypothesis,
    InvestigationStatus,
    new_id,
)
from debugging_engine.domain.policies import (
    MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
    MAX_OBSERVATION_CHARS,
    STALL_CYCLES_BEFORE_ESCALATION,
)
from debugging_engine.domain.validation import ValidationError, apply_event
from debugging_engine.infrastructure.verify import truncate_observation
from debugging_engine.runtime.stubs.scenarios import (
    scenario_evidence_bloat,
    scenario_happy_cache,
    scenario_hypothesis_flood,
    scenario_starvation,
)
from fixtures import cache_miss_workspace


def test_truncate_observation():
    text = "a" * (MAX_OBSERVATION_CHARS + 500)
    out = truncate_observation(text)
    assert len(out) <= MAX_OBSERVATION_CHARS
    assert out.endswith("...[truncated]")


def test_hypothesis_budget_validation(tmp_path: Path):
    workspace, issue = cache_miss_workspace(tmp_path)
    svc = CaseService(workspace, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(issue)
    unk = next(iter(svc.engine.project(case_id).unknowns))  # type: ignore[union-attr]
    for i in range(MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.HYPOTHESIS_PROPOSED,
                    timestamp="2026-07-29T00:00:00Z",
                    producer=AgentRole.ANALYST,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": f"h{i}",
                        "explanation": "e",
                    },
                )
            ]
        )
    with pytest.raises(ValidationError, match="budget"):
        svc.submit(
            [
                DomainEvent(
                    case_id=case_id,
                    event_type=EventType.HYPOTHESIS_PROPOSED,
                    timestamp="2026-07-29T00:00:00Z",
                    producer=AgentRole.ANALYST,
                    payload={
                        "id": new_id(),
                        "unknown_id": unk,
                        "title": "overflow",
                        "explanation": "e",
                    },
                )
            ]
        )


def test_judge_no_logging_heuristic():
    state = CaseState(
        case_id="c1",
        title="t",
        status=InvestigationStatus.ACTIVE,
        unknowns={
            "u1": Unknown(id="u1", title="Why?", status=UnknownStatus.ACTIVE),
        },
        hypotheses={
            "h1": Hypothesis(
                id="h1",
                unknown_id="u1",
                title="Completely unrelated title",
                explanation="no magic words",
                status=HypothesisStatus.PROPOSED,
            )
        },
    )
    task = schedule_next_task(state)
    # Structural rule: one competing hyp and no evidence -> Adversary
    assert task.role == AgentRole.ADVERSARY


def test_stall_escalation_task(tmp_path: Path):
    workspace, issue = cache_miss_workspace(tmp_path)
    svc = CaseService(workspace, store_root=tmp_path / "cases")
    case_id, _ = svc.open_issue(issue)
    unk = next(iter(svc.engine.project(case_id).unknowns))  # type: ignore[union-attr]
    # Two Analyst hypotheses (no forged Adversary producer) — skips pre-evidence
    # Adversary gate when competing >= 2 and no proposed experiments.
    svc.submit(
        [
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp="2026-07-29T00:00:00Z",
                producer=AgentRole.ANALYST,
                payload={
                    "id": new_id(),
                    "unknown_id": unk,
                    "title": "a",
                    "explanation": "e",
                },
            ),
            DomainEvent(
                case_id=case_id,
                event_type=EventType.HYPOTHESIS_PROPOSED,
                timestamp="2026-07-29T00:00:00Z",
                producer=AgentRole.ANALYST,
                payload={
                    "id": new_id(),
                    "unknown_id": unk,
                    "title": "b",
                    "explanation": "e",
                },
            ),
        ]
    )
    task = None
    for _ in range(STALL_CYCLES_BEFORE_ESCALATION + 2):
        task = svc.next_task(case_id)
    assert task is not None
    assert EventType.INVESTIGATION_ESCALATED.value in task["allowed_event_types"]
    assert task["role"] in {AgentRole.HUMAN.value, AgentRole.JUDGE.value}


def test_phase2_scenarios(tmp_path: Path):
    workspace, issue = cache_miss_workspace(tmp_path)
    svc = CaseService(workspace, store_root=tmp_path / "cases")
    assert scenario_hypothesis_flood(svc, issue)["ok"]
    svc2 = CaseService(workspace, store_root=tmp_path / "cases2")
    assert scenario_starvation(svc2, issue)["ok"]
    svc3 = CaseService(workspace, store_root=tmp_path / "cases3")
    assert scenario_evidence_bloat(svc3, issue)["ok"]
    svc4 = CaseService(workspace, store_root=tmp_path / "cases4")
    assert scenario_happy_cache(svc4, issue)["ok"]

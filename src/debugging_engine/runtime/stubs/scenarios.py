"""Phase 2 stress scenarios for architectural validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from debugging_engine.application.metrics import CaseMetrics, compute_case_metrics
from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.domain.policies import (
    MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
    MAX_OBSERVATION_CHARS,
    STALL_CYCLES_BEFORE_ESCALATION,
)
from debugging_engine.domain.validation import ValidationError
from debugging_engine.runtime.stubs.demo import run_stub_investigation


def _ev(case_id: str, et: EventType, producer: str, payload: dict) -> DomainEvent:
    return DomainEvent(
        case_id=case_id,
        event_type=et,
        timestamp=utc_now(),
        producer=producer,
        payload=payload,
    )


def scenario_happy_cache(service: CaseService, issue_path: Path) -> dict[str, Any]:
    result = run_stub_investigation(service, issue_path)
    metrics = compute_case_metrics(service.store, result["case_id"])
    ok = result["status"] == "RESOLVED"
    return {
        "scenario": "happy_cache",
        "case_id": result["case_id"],
        "ok": ok,
        "failure": None if ok else f"expected RESOLVED got {result['status']}",
        "notes": "Baseline stub investigation of asymmetric cache key normalization.",
        "metrics": metrics.model_dump(),
    }


def scenario_hypothesis_flood(service: CaseService, issue_path: Path) -> dict[str, Any]:
    case_id, _ = service.open_issue(issue_path)
    state = service.engine.project(case_id)
    assert state is not None
    unknown_id = next(iter(state.unknowns))
    accepted = 0
    rejected = False
    for i in range(MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN + 3):
        try:
            service.submit(
                [
                    _ev(
                        case_id,
                        EventType.HYPOTHESIS_PROPOSED,
                        AgentRole.ANALYST,
                        {
                            "id": new_id(),
                            "unknown_id": unknown_id,
                            "title": f"Flood hypothesis {i}",
                            "explanation": f"Noise explanation {i}",
                        },
                    )
                ]
            )
            accepted += 1
        except ValidationError as exc:
            rejected = "budget" in str(exc).lower() or "exceeded" in str(exc).lower()
            break
    metrics = compute_case_metrics(service.store, case_id)
    # Merge meta into metrics via status
    status = service.status(case_id)
    metrics.scheduling_cycles = int(status["decision_state"].get("scheduling_cycles", 0))
    metrics.stall_cycles = int(status["decision_state"].get("stall_cycles", 0))
    ok = accepted == MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN and rejected
    return {
        "scenario": "hypothesis_flood",
        "case_id": case_id,
        "ok": ok,
        "failure": None
        if ok
        else f"accepted={accepted} rejected={rejected} budget={MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN}",
        "notes": (
            f"Submitted hypotheses until budget ({MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN}); "
            "further HypothesisProposed must fail validation."
        ),
        "metrics": metrics.model_dump(),
    }


def scenario_starvation(service: CaseService, issue_path: Path) -> dict[str, Any]:
    case_id, _ = service.open_issue(issue_path)
    state = service.engine.project(case_id)
    assert state is not None
    unknown_id = next(iter(state.unknowns))
    hyp_id = new_id()
    service.submit(
        [
            _ev(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": hyp_id,
                    "unknown_id": unknown_id,
                    "title": "Unfalsifiable guess",
                    "explanation": "No cheap way to test.",
                },
            ),
            _ev(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ADVERSARY,
                {
                    "id": new_id(),
                    "unknown_id": unknown_id,
                    "title": "Competing unfalsifiable guess",
                    "explanation": "Also hard to test.",
                },
            ),
            _ev(
                case_id,
                EventType.EXPERIMENT_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": new_id(),
                    "unknown_id": unknown_id,
                    "title": "Risky useless experiment",
                    "information_gain": "MINIMAL",
                    "cost": "CRITICAL",
                    "affected_hypotheses": [hyp_id],
                    "verification_spec": {
                        "command": ["python", "-m", "pytest", "tests/test_cache.py", "-q"],
                        "expected_exit_code": 0,
                    },
                },
            ),
        ]
    )
    # Poll next until Judge asks to escalate (stall threshold)
    last_task = None
    for _ in range(STALL_CYCLES_BEFORE_ESCALATION + 5):
        last_task = service.next_task(case_id)
        if EventType.INVESTIGATION_ESCALATED.value in last_task.get("allowed_event_types", []):
            break
    # Actually escalate
    service.submit(
        [
            _ev(
                case_id,
                EventType.INVESTIGATION_ESCALATED,
                AgentRole.JUDGE,
                {"reason": "Starvation: no productive experiments within stall threshold."},
            )
        ]
    )
    status = service.status(case_id)
    metrics = compute_case_metrics(service.store, case_id)
    metrics.scheduling_cycles = int(status["decision_state"].get("scheduling_cycles", 0))
    metrics.stall_cycles = int(status["decision_state"].get("stall_cycles", 0))
    metrics.status = status["status"]
    ok = status["status"] == "ESCALATED" and last_task is not None
    return {
        "scenario": "starvation",
        "case_id": case_id,
        "ok": ok,
        "failure": None if ok else f"status={status['status']} task={last_task}",
        "notes": (
            f"MINIMAL/CRITICAL-only path; after {STALL_CYCLES_BEFORE_ESCALATION} stall cycles "
            "Judge offers escalation; scenario submits InvestigationEscalated."
        ),
        "metrics": metrics.model_dump(),
    }


def scenario_evidence_bloat(service: CaseService, issue_path: Path) -> dict[str, Any]:
    case_id, _ = service.open_issue(issue_path)
    state = service.engine.project(case_id)
    assert state is not None
    unknown_id = next(iter(state.unknowns))
    hyp_id = new_id()
    exp_id = new_id()
    # Create a temp verbose test that prints a huge line
    verbose_test = service.repo_root / "tests" / "_tmp_verbose_test.py"
    verbose_test.parent.mkdir(parents=True, exist_ok=True)
    verbose_test.write_text(
        "def test_verbose():\n"
        "    print('X' * 8000)\n"
        "    assert False\n",
        encoding="utf-8",
    )
    try:
        service.submit(
            [
                _ev(
                    case_id,
                    EventType.HYPOTHESIS_PROPOSED,
                    AgentRole.ANALYST,
                    {
                        "id": hyp_id,
                        "unknown_id": unknown_id,
                        "title": "Noise",
                        "explanation": "Placeholder",
                    },
                ),
                _ev(
                    case_id,
                    EventType.HYPOTHESIS_PROPOSED,
                    AgentRole.ADVERSARY,
                    {
                        "id": new_id(),
                        "unknown_id": unknown_id,
                        "title": "Alt",
                        "explanation": "Placeholder alt",
                    },
                ),
                _ev(
                    case_id,
                    EventType.EXPERIMENT_PROPOSED,
                    AgentRole.ANALYST,
                    {
                        "id": exp_id,
                        "unknown_id": unknown_id,
                        "title": "Verbose failing test",
                        "information_gain": "HIGH",
                        "cost": "LOW",
                        "affected_hypotheses": [hyp_id],
                        "verification_spec": {
                            "command": [
                                "python",
                                "-m",
                                "pytest",
                                "tests/_tmp_verbose_test.py",
                                "-q",
                                "-s",
                            ],
                            "expected_exit_code": 0,
                        },
                    },
                ),
                _ev(
                    case_id,
                    EventType.EXPERIMENT_APPROVED,
                    AgentRole.JUDGE,
                    {"experiment_id": exp_id, "authority": "Judge"},
                ),
            ]
        )
        service.verify(case_id, exp_id)
        state = service.engine.project(case_id)
        assert state is not None
        evidence = list(state.evidence.values())
        assert evidence
        obs_len = len(evidence[-1].observation)
        truncated = evidence[-1].attributes.get("observation_truncated") is True
        metrics = compute_case_metrics(service.store, case_id)
        ok = obs_len <= MAX_OBSERVATION_CHARS and truncated
        return {
            "scenario": "evidence_bloat",
            "case_id": case_id,
            "ok": ok,
            "failure": None
            if ok
            else f"obs_len={obs_len} truncated={truncated} max={MAX_OBSERVATION_CHARS}",
            "notes": (
                f"Verbose pytest output must be truncated to {MAX_OBSERVATION_CHARS} chars "
                "in EvidenceRecorded payloads."
            ),
            "metrics": metrics.model_dump(),
        }
    finally:
        if verbose_test.exists():
            verbose_test.unlink()


SCENARIOS: list[tuple[str, Callable[[CaseService, Path], dict[str, Any]]]] = [
    ("happy_cache", scenario_happy_cache),
    ("hypothesis_flood", scenario_hypothesis_flood),
    ("starvation", scenario_starvation),
    ("evidence_bloat", scenario_evidence_bloat),
]


def run_all_scenarios(service: CaseService, issue_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _name, fn in SCENARIOS:
        rows.append(fn(service, issue_path))
    return rows

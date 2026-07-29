"""Deterministic stub driver that walks the seeded cache issue to RootCauseAccepted."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id


FIXED_CACHE = '''\
"""Tiny in-memory cache used as the Debugging Engine investigation subject."""


def normalize_key(key: str) -> str:
    return key.strip().lower()


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        self._store[normalize_key(key)] = value

    def get(self, key: str) -> object | None:
        return self._store.get(normalize_key(key))

    def __contains__(self, key: str) -> bool:
        return normalize_key(key) in self._store
'''


def _event(case_id: str, et: EventType, producer: str, payload: dict, causation_id: str | None = None) -> DomainEvent:
    return DomainEvent(
        case_id=case_id,
        event_type=et,
        timestamp=utc_now(),
        producer=producer,
        causation_id=causation_id,
        payload=payload,
    )


def run_stub_investigation(service: CaseService, issue_path: Path) -> dict:
    """Drive a full investigation using stub event submissions (CI / demo)."""
    case_id, _ = service.open_issue(issue_path)
    steps: list[str] = []

    state = service.engine.project(case_id)
    assert state is not None
    unknown_id = next(iter(state.unknowns))
    hyp_cache = new_id()
    hyp_logging = new_id()
    exp_observe = new_id()
    exp_fix = new_id()

    # Bootstrap Analyst task from open — propose hyp + observational experiment
    service.submit(
        [
            _event(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": hyp_cache,
                    "unknown_id": unknown_id,
                    "title": "Asymmetric cache key normalization",
                    "explanation": "Cache.set stores raw keys while Cache.get lowercases, so lookups miss.",
                    "assumptions": ["Failure is deterministic for mixed-case keys"],
                },
            ),
            _event(
                case_id,
                EventType.EXPERIMENT_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": exp_observe,
                    "unknown_id": unknown_id,
                    "title": "Reproduce failing cache tests",
                    "description": "Run cache unit tests without code changes.",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hyp_cache],
                    "expected_observations": ["pytest fails on mixed-case key lookup"],
                    "experiment_class": "observational",
                    "verification_spec": {
                        "command": ["python", "-m", "pytest", "tests/test_cache.py", "-q"],
                        "expected_exit_code": 0,
                        "working_directory": ".",
                        "description": "Cache unit tests should pass",
                    },
                },
            ),
        ]
    )
    steps.append("analyst_proposed")

    task = service.next_task(case_id)
    assert task["role"] == AgentRole.ADVERSARY.value
    service.submit(
        [
            _event(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ADVERSARY,
                {
                    "id": hyp_logging,
                    "unknown_id": unknown_id,
                    "title": "Verbose logging overhead",
                    "explanation": "Unrelated logging configuration might explain perceived misses.",
                    "assumptions": ["Logging is enabled in the workspace"],
                },
            ),
        ]
    )
    steps.append("adversary_challenged")

    task = service.next_task(case_id)
    assert task["role"] == AgentRole.JUDGE.value
    service.submit(
        [
            _event(
                case_id,
                EventType.EXPERIMENT_APPROVED,
                AgentRole.JUDGE,
                {"experiment_id": exp_observe, "authority": "Judge"},
            ),
        ]
    )
    steps.append("approved_observe")

    task = service.next_task(case_id)
    assert task["role"] == AgentRole.VERIFIER.value
    service.verify(case_id, exp_observe)
    steps.append("verified_observe_failed")

    state = service.engine.project(case_id)
    assert state is not None
    observe_exp = state.experiments[exp_observe]
    assert observe_exp.status.value == "FAILED"
    evidence_ids = list(state.evidence.keys())
    assert evidence_ids
    ev_id = evidence_ids[-1]

    task = service.next_task(case_id)
    assert task["role"] == AgentRole.ANALYST.value
    service.submit(
        [
            _event(
                case_id,
                EventType.INTERPRETATION_SUBMITTED,
                AgentRole.ANALYST,
                {
                    "id": new_id(),
                    "evidence_id": ev_id,
                    "hypothesis_id": hyp_cache,
                    "outcome": "SUPPORTS",
                    "rationale": "Failing mixed-case lookup matches asymmetric normalization.",
                },
            ),
            _event(
                case_id,
                EventType.INTERPRETATION_SUBMITTED,
                AgentRole.ADVERSARY,
                {
                    "id": new_id(),
                    "evidence_id": ev_id,
                    "hypothesis_id": hyp_logging,
                    "outcome": "INCONCLUSIVE",
                    "rationale": "Test failure does not mention logging; need discriminating fix experiment.",
                },
            ),
            _event(
                case_id,
                EventType.EXPERIMENT_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": exp_fix,
                    "unknown_id": unknown_id,
                    "title": "Normalize keys on set and get",
                    "description": "Apply patch so both paths use normalize_key.",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hyp_cache, hyp_logging],
                    "expected_observations": ["pytest passes after symmetric normalization"],
                    "experiment_class": "intervention",
                    "verification_spec": {
                        "command": ["python", "-m", "pytest", "tests/test_cache.py", "-q"],
                        "expected_exit_code": 0,
                        "working_directory": ".",
                        "description": "Cache unit tests should pass after fix",
                    },
                    "patch": {"cache.py": FIXED_CACHE},
                },
            ),
        ]
    )
    steps.append("interpret_and_propose_fix")

    task = service.next_task(case_id)
    assert task["role"] == AgentRole.JUDGE.value
    service.submit(
        [
            _event(
                case_id,
                EventType.EXPERIMENT_APPROVED,
                AgentRole.JUDGE,
                {"experiment_id": exp_fix, "authority": "Judge"},
            ),
        ]
    )

    task = service.next_task(case_id)
    # Implementer if patch not yet applied, else Verifier
    assert task["role"] in {AgentRole.IMPLEMENTER.value, AgentRole.VERIFIER.value}
    service.verify(case_id, exp_fix)
    steps.append("verified_fix")

    state = service.engine.project(case_id)
    assert state is not None
    fix_evidence = [e for e in state.evidence.values() if e.experiment_id == exp_fix]
    assert fix_evidence
    fix_ev = fix_evidence[-1].id
    passed = fix_evidence[-1].attributes.get("passed") is True

    if passed:
        task = service.next_task(case_id)
        assert task["role"] == AgentRole.ANALYST.value
        service.submit(
            [
                _event(
                    case_id,
                    EventType.INTERPRETATION_SUBMITTED,
                    AgentRole.ANALYST,
                    {
                        "id": new_id(),
                        "evidence_id": fix_ev,
                        "hypothesis_id": hyp_cache,
                        "outcome": "SUPPORTS",
                        "rationale": "Fixing asymmetric normalization makes tests pass.",
                    },
                ),
            ]
        )
        # Re-engage Adversary on unrebutted SUPPORTS before root-cause acceptance.
        task = service.next_task(case_id)
        assert task["role"] == AgentRole.ADVERSARY.value
        service.submit(
            [
                _event(
                    case_id,
                    EventType.INTERPRETATION_SUBMITTED,
                    AgentRole.ADVERSARY,
                    {
                        "id": new_id(),
                        "evidence_id": fix_ev,
                        "hypothesis_id": hyp_logging,
                        "outcome": "WEAKENS",
                        "rationale": "Passing fix falsifies logging-overhead alternative.",
                    },
                ),
            ]
        )
        task = service.next_task(case_id)
        assert task["role"] == AgentRole.JUDGE.value
        service.submit(
            [
                _event(
                    case_id,
                    EventType.HYPOTHESIS_REJECTED,
                    AgentRole.JUDGE,
                    {
                        "hypothesis_id": hyp_logging,
                        "reason": "Discriminating fix experiment falsified logging hypothesis.",
                    },
                ),
                _event(
                    case_id,
                    EventType.UNKNOWN_RESOLVED,
                    AgentRole.JUDGE,
                    {"unknown_id": unknown_id},
                ),
                _event(
                    case_id,
                    EventType.ROOT_CAUSE_ACCEPTED,
                    AgentRole.JUDGE,
                    {
                        "hypothesis_id": hyp_cache,
                        "rationale": (
                            "Asymmetric key normalization; verified by failing then "
                            "passing tests after symmetric normalize_key."
                        ),
                        "authority": "Judge",
                    },
                ),
            ]
        )
        steps.append("root_cause_accepted")
    else:
        task = service.next_task(case_id)
        # Escalation may be offered on Judge or Analyst stall tasks.
        if EventType.INVESTIGATION_ESCALATED.value not in task.get("allowed_event_types", []):
            # Force a Judge/Analyst stall handoff that permits escalation.
            for _ in range(8):
                task = service.next_task(case_id)
                if EventType.INVESTIGATION_ESCALATED.value in task.get("allowed_event_types", []):
                    break
        service.submit(
            [
                _event(
                    case_id,
                    EventType.INVESTIGATION_ESCALATED,
                    AgentRole.JUDGE,
                    {"reason": "Fix experiment did not pass; escalate."},
                ),
            ]
        )
        steps.append("escalated")

    final = service.status(case_id)
    return {
        "case_id": case_id,
        "steps": steps,
        "status": final["status"],
        "decision_state": final["decision_state"],
    }

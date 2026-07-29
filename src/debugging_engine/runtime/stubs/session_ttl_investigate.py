"""Drive the investigate skill loop on the session_ttl fixture; record role announcements."""

from __future__ import annotations

from pathlib import Path

from debugging_engine.application.service import CaseService, utc_now
from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, new_id
from debugging_engine.runtime.stubs.role_announce import format_role_announcement


FIXED_SESSION = '''\
"""In-memory session store used as a Debugging Engine investigation subject.

Sessions should stay alive while clients keep calling ``touch()`` within the TTL.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class Session:
    session_id: str
    created_at: float
    last_seen: float
    user_id: str


class SessionStore:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def create(self, session_id: str, user_id: str, *, now: float | None = None) -> Session:
        t = monotonic() if now is None else now
        session = Session(
            session_id=session_id,
            created_at=t,
            last_seen=t,
            user_id=user_id,
        )
        self._sessions[session_id] = session
        return session

    def touch(self, session_id: str, *, now: float | None = None) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        t = monotonic() if now is None else now
        session.last_seen = t
        return session

    def is_active(self, session_id: str, *, now: float | None = None) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        t = monotonic() if now is None else now
        # Expiry is relative to last activity (touch), not creation time.
        return (t - session.last_seen) <= self._ttl

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)
'''


def _event(case_id: str, et: EventType, producer: str, payload: dict) -> DomainEvent:
    return DomainEvent(
        case_id=case_id,
        event_type=et,
        timestamp=utc_now(),
        producer=producer,
        payload=payload,
    )


def run_session_ttl_investigate(service: CaseService, issue_path: Path) -> dict:
    """Full investigate-style loop with every role handoff announced and recorded.

    Mirrors ``debugging-engine-investigate``: open → next → announce → act → submit → …
    Returns status plus the ordered list of chat announcement lines.
    """
    case_id, _ = service.open_issue(issue_path)
    announcements: list[str] = []
    roles_seen: list[str] = []

    def announce(task: dict) -> dict:
        line = format_role_announcement(task)
        announcements.append(line)
        roles_seen.append(str(task["role"]))
        return task

    state = service.engine.project(case_id)
    assert state is not None
    unknown_id = next(iter(state.unknowns))
    hyp_created = new_id()
    hyp_clock = new_id()
    exp_observe = new_id()
    exp_fix = new_id()

    # Bootstrap Analyst (open already set Analyst propose Task)
    announcements.append(
        format_role_announcement(
            {
                "role": AgentRole.ANALYST.value,
                "objective": (
                    "Propose hypotheses and ExperimentProposed events for open unknowns. "
                    "Do not approve, verify, or implement — call next after submit."
                ),
            }
        )
    )
    roles_seen.append(AgentRole.ANALYST.value)

    service.submit(
        [
            _event(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": hyp_created,
                    "unknown_id": unknown_id,
                    "title": "is_active uses created_at instead of last_seen",
                    "explanation": (
                        "touch() updates last_seen but is_active subtracts created_at, "
                        "so refreshed sessions still expire on the original creation clock."
                    ),
                    "assumptions": [
                        "TTL semantics intend sliding window from last activity",
                        "touch() is the activity signal",
                    ],
                },
            ),
            _event(
                case_id,
                EventType.EXPERIMENT_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": exp_observe,
                    "unknown_id": unknown_id,
                    "title": "Reproduce session TTL tests",
                    "description": "Run session unit tests without code changes.",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hyp_created],
                    "expected_observations": [
                        "test_touch_extends_session_lifetime fails",
                        "test_repeated_touch_keeps_long_lived_session fails",
                    ],
                    "experiment_class": "observational",
                    "verification_spec": {
                        "command": ["python", "-m", "pytest", "tests/test_session.py", "-q"],
                        "expected_exit_code": 0,
                        "working_directory": ".",
                    },
                },
            ),
        ]
    )

    task = announce(service.next_task(case_id))
    assert task["role"] == AgentRole.ADVERSARY.value
    service.submit(
        [
            _event(
                case_id,
                EventType.HYPOTHESIS_PROPOSED,
                AgentRole.ADVERSARY,
                {
                    "id": hyp_clock,
                    "unknown_id": unknown_id,
                    "title": "Caller passes inconsistent now timestamps",
                    "explanation": (
                        "Alternative: tests or callers inject non-monotonic now values, "
                        "so the store looks broken while the implementation is fine."
                    ),
                    "assumptions": ["Tests control now= explicitly and consistently"],
                    "parent_id": None,
                },
            ),
        ]
    )

    task = announce(service.next_task(case_id))
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

    task = announce(service.next_task(case_id))
    assert task["role"] == AgentRole.VERIFIER.value
    service.verify(case_id, exp_observe)

    state = service.engine.project(case_id)
    assert state is not None
    assert state.experiments[exp_observe].status.value == "FAILED"
    ev_id = list(state.evidence.keys())[-1]

    task = announce(service.next_task(case_id))
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
                    "hypothesis_id": hyp_created,
                    "outcome": "SUPPORTS",
                    "rationale": (
                        "Failing touch-extension tests match created_at-based expiry; "
                        "tests inject consistent now= so clock-injection is unlikely."
                    ),
                },
            ),
            _event(
                case_id,
                EventType.INTERPRETATION_SUBMITTED,
                AgentRole.ADVERSARY,
                {
                    "id": new_id(),
                    "evidence_id": ev_id,
                    "hypothesis_id": hyp_clock,
                    "outcome": "WEAKENS",
                    "rationale": (
                        "Objection category: Missing Evidence — failing tests use explicit "
                        "monotonic now= sequences; no evidence of inconsistent clocks."
                    ),
                },
            ),
            _event(
                case_id,
                EventType.EXPERIMENT_PROPOSED,
                AgentRole.ANALYST,
                {
                    "id": exp_fix,
                    "unknown_id": unknown_id,
                    "title": "Expire sessions from last_seen",
                    "description": "Patch is_active to compare against last_seen.",
                    "information_gain": "HIGH",
                    "cost": "LOW",
                    "affected_hypotheses": [hyp_created, hyp_clock],
                    "expected_observations": ["pytest passes after last_seen-based expiry"],
                    "experiment_class": "intervention",
                    "verification_spec": {
                        "command": ["python", "-m", "pytest", "tests/test_session.py", "-q"],
                        "expected_exit_code": 0,
                        "working_directory": ".",
                    },
                    "patch": {"session.py": FIXED_SESSION},
                },
            ),
        ]
    )

    task = announce(service.next_task(case_id))
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

    task = announce(service.next_task(case_id))
    assert task["role"] == AgentRole.IMPLEMENTER.value
    # Materialize patch via verify (auto PatchApplied) after announcing Implementer,
    # matching skill: announce Implementer, then Verifier for verify.
    # Explicit PatchApplied path is also valid; verify applies when missing.
    service.submit(
        [
            _event(
                case_id,
                EventType.PATCH_APPLIED,
                AgentRole.IMPLEMENTER,
                {"experiment_id": exp_fix, "paths": ["session.py"]},
            ),
        ]
    )
    # Write the fixed file (Implementer work outside the kernel)
    (service.repo_root / "session.py").write_text(FIXED_SESSION, encoding="utf-8")

    task = announce(service.next_task(case_id))
    assert task["role"] == AgentRole.VERIFIER.value
    service.verify(case_id, exp_fix)

    state = service.engine.project(case_id)
    assert state is not None
    fix_evidence = [e for e in state.evidence.values() if e.experiment_id == exp_fix]
    assert fix_evidence and fix_evidence[-1].attributes.get("passed") is True
    fix_ev = fix_evidence[-1].id

    task = announce(service.next_task(case_id))
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
                    "hypothesis_id": hyp_created,
                    "outcome": "SUPPORTS",
                    "rationale": "Switching expiry to last_seen makes all session tests pass.",
                },
            ),
        ]
    )

    task = announce(service.next_task(case_id))
    assert task["role"] == AgentRole.JUDGE.value
    service.submit(
        [
            _event(
                case_id,
                EventType.HYPOTHESIS_REJECTED,
                AgentRole.JUDGE,
                {
                    "hypothesis_id": hyp_clock,
                    "reason": "Discriminating fix falsified inconsistent-now hypothesis.",
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
                    "hypothesis_id": hyp_created,
                    "rationale": (
                        "is_active compared against created_at while touch updated last_seen; "
                        "verified by failing observational tests then passing after last_seen fix."
                    ),
                    "authority": "Judge",
                },
            ),
        ]
    )

    final = service.status(case_id)
    return {
        "case_id": case_id,
        "status": final["status"],
        "announcements": announcements,
        "roles_seen": roles_seen,
        "decision_state": final["decision_state"],
        "root_cause_hypothesis_id": final["decision_state"].get("root_cause_hypothesis_id"),
    }

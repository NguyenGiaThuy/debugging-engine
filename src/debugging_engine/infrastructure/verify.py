from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from debugging_engine.domain.models import AgentRole, DomainEvent, EventType, ExperimentStatus, new_id
from debugging_engine.domain.policies import MAX_OBSERVATION_CHARS
from debugging_engine.domain.validation import ValidationError
from debugging_engine.infrastructure.paths import resolve_under_root
from debugging_engine.infrastructure.store import ProjectionEngine


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def truncate_observation(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "\n...[truncated]"


def _resolve_command(command: list[str]) -> list[str]:
    """Prefer the current interpreter for python module runners."""
    if not command:
        return command
    if command[0] == "pytest":
        return [sys.executable, "-m", "pytest", *command[1:]]
    if command[0] == "python":
        return [sys.executable, *command[1:]]
    return command


def _fail_experiment(
    engine: ProjectionEngine,
    case_id: str,
    experiment_id: str,
    *,
    reason: str,
    causation_id: str | None,
    observation: str | None = None,
) -> DomainEvent:
    payload: dict = {"experiment_id": experiment_id, "reason": reason}
    if observation is not None:
        payload["observation"] = observation
    fail = DomainEvent(
        case_id=case_id,
        event_type=EventType.VERIFICATION_FAILED,
        timestamp=utc_now(),
        producer=AgentRole.VERIFIER,
        causation_id=causation_id,
        payload=payload,
    )
    engine.append_validated(fail)
    return fail


def run_verification(
    engine: ProjectionEngine,
    case_id: str,
    experiment_id: str,
    repo_root: Path,
) -> list[DomainEvent]:
    """Execute Verification Spec for an experiment; return Evidence / failure events.

    On unexpected exit code or missing spec the experiment ends in FAILED (not COMPLETED).
    """
    state = engine.project(case_id)
    if state is None:
        raise ValueError(f"Unknown case {case_id}")
    exp = state.experiments.get(experiment_id)
    if exp is None:
        raise ValueError(f"Unknown experiment {experiment_id}")

    events: list[DomainEvent] = []
    causation: str | None = None
    root = repo_root.resolve()

    if exp.status == ExperimentStatus.APPROVED:
        ev = DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_SCHEDULED,
            timestamp=utc_now(),
            producer=AgentRole.JUDGE,
            payload={"experiment_id": experiment_id},
        )
        engine.append_validated(ev)
        events.append(ev)
        causation = ev.event_id
        exp = engine.project(case_id).experiments[experiment_id]  # type: ignore[union-attr]

    if exp.status == ExperimentStatus.SCHEDULED:
        ev = DomainEvent(
            case_id=case_id,
            event_type=EventType.EXPERIMENT_STARTED,
            timestamp=utc_now(),
            producer=AgentRole.VERIFIER,
            causation_id=causation,
            payload={"experiment_id": experiment_id},
        )
        engine.append_validated(ev)
        events.append(ev)
        causation = ev.event_id

    state = engine.project(case_id)
    assert state is not None
    exp = state.experiments[experiment_id]
    already_patched = any(
        isinstance(p, dict) and p.get("experiment_id") == experiment_id
        for p in state.decision_state.get("patches", [])
    )
    if exp.patch and not already_patched:
        try:
            for rel_path, content in exp.patch.items():
                target = resolve_under_root(root, rel_path, what="patch path")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        except ValidationError as exc:
            fail = _fail_experiment(
                engine,
                case_id,
                experiment_id,
                reason="PathEscape",
                causation_id=causation,
                observation=str(exc),
            )
            events.append(fail)
            return events
        patch_ev = DomainEvent(
            case_id=case_id,
            event_type=EventType.PATCH_APPLIED,
            timestamp=utc_now(),
            producer=AgentRole.IMPLEMENTER,
            causation_id=causation,
            payload={"experiment_id": experiment_id, "paths": list(exp.patch.keys())},
        )
        engine.append_validated(patch_ev)
        events.append(patch_ev)
        causation = patch_ev.event_id

    spec = exp.verification_spec
    if spec is None:
        fail = _fail_experiment(
            engine,
            case_id,
            experiment_id,
            reason="MissingVerificationSpec",
            causation_id=causation,
        )
        events.append(fail)
        return events

    try:
        cwd = resolve_under_root(
            root,
            spec.working_directory if spec.working_directory else ".",
            what="working_directory",
        )
        if not cwd.is_dir():
            # Allow missing leaf only if it is the repo root; otherwise fail closed.
            if cwd == root:
                cwd.mkdir(parents=True, exist_ok=True)
            else:
                raise ValidationError(
                    "working_directory does not exist",
                    {"path": spec.working_directory},
                )
    except ValidationError as exc:
        fail = _fail_experiment(
            engine,
            case_id,
            experiment_id,
            reason="PathEscape",
            causation_id=causation,
            observation=str(exc),
        )
        events.append(fail)
        return events

    cmd = _resolve_command(list(spec.command))
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    raw_observation = (
        f"exit_code={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    observation = truncate_observation(raw_observation)
    evidence_id = new_id()
    success = result.returncode == spec.expected_exit_code
    attrs = {
        "exit_code": result.returncode,
        "passed": success,
        "observation_truncated": len(raw_observation) > len(observation),
        "raw_observation_chars": len(raw_observation),
    }

    state = engine.project(case_id)
    assert state is not None
    if state.experiments[experiment_id].status != ExperimentStatus.RUNNING:
        raise RuntimeError(f"Experiment {experiment_id} not RUNNING before evidence")

    # Evidence is always recorded while RUNNING; terminal status follows.
    ev_rec = DomainEvent(
        case_id=case_id,
        event_type=EventType.EVIDENCE_RECORDED,
        timestamp=utc_now(),
        producer=AgentRole.VERIFIER,
        causation_id=causation,
        payload={
            "id": evidence_id,
            "experiment_id": experiment_id,
            "observation": observation,
            "provenance": "verifier",
            "category": "Test Result",
            "collection_method": " ".join(spec.command),
            "attributes": attrs,
        },
    )
    engine.append_validated(ev_rec)
    events.append(ev_rec)

    if not success:
        fail = _fail_experiment(
            engine,
            case_id,
            experiment_id,
            reason="UnexpectedExitCode",
            causation_id=ev_rec.event_id,
            observation=observation,
        )
        events.append(fail)
        return events

    done = DomainEvent(
        case_id=case_id,
        event_type=EventType.EXPERIMENT_COMPLETED,
        timestamp=utc_now(),
        producer=AgentRole.VERIFIER,
        causation_id=ev_rec.event_id,
        payload={"experiment_id": experiment_id},
    )
    engine.append_validated(done)
    events.append(done)
    return events

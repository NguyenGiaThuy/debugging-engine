from __future__ import annotations

from typing import Any

from smadw.domain.models import (
    CaseState,
    DomainEvent,
    EventType,
    Evidence,
    Experiment,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    Interpretation,
    InterpretationOutcome,
    InvestigationStatus,
    Unknown,
    UnknownStatus,
    VerificationSpec,
)
from smadw.domain.transitions import (
    can_promote_hypothesis,
    can_transition_experiment,
    can_transition_unknown,
)


class ValidationError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def validate_event(state: CaseState | None, event: DomainEvent) -> None:
    """Validate event against current Case State before append."""
    et = event.event_type
    payload = event.payload

    if et == EventType.CASE_CREATED:
        if state is not None and state.event_count > 0:
            raise ValidationError("Case already exists")
        if not payload.get("title"):
            raise ValidationError("CaseCreated requires title")
        return

    if state is None:
        raise ValidationError("Case does not exist; emit CaseCreated first")

    if event.case_id != state.case_id:
        raise ValidationError("case_id mismatch")

    if et == EventType.UNKNOWN_DISCOVERED:
        if not payload.get("id") or not payload.get("title"):
            raise ValidationError("UnknownDiscovered requires id and title")
        if payload["id"] in state.unknowns:
            raise ValidationError("Unknown already exists", {"id": payload["id"]})
        return

    if et == EventType.UNKNOWN_RESOLVED:
        uid = payload.get("unknown_id")
        if not uid or uid not in state.unknowns:
            raise ValidationError("UnknownResolved requires existing unknown_id")
        unk = state.unknowns[uid]
        if not can_transition_unknown(unk.status, UnknownStatus.RESOLVED):
            raise ValidationError(f"Invalid unknown transition {unk.status} -> RESOLVED")
        return

    if et == EventType.HYPOTHESIS_PROPOSED:
        for field in ("id", "unknown_id", "title", "explanation"):
            if not payload.get(field):
                raise ValidationError(f"HypothesisProposed requires {field}")
        if payload["unknown_id"] not in state.unknowns:
            raise ValidationError("target Unknown does not exist")
        if payload["id"] in state.hypotheses:
            raise ValidationError("Hypothesis already exists")
        return

    if et == EventType.HYPOTHESIS_PROMOTED:
        hid = payload.get("hypothesis_id")
        target = payload.get("to_status")
        if not hid or hid not in state.hypotheses:
            raise ValidationError("HypothesisPromoted requires existing hypothesis_id")
        if not target:
            raise ValidationError("HypothesisPromoted requires to_status")
        hyp = state.hypotheses[hid]
        try:
            target_status = HypothesisStatus(target)
        except ValueError as exc:
            raise ValidationError(f"Invalid hypothesis status {target}") from exc
        if not can_promote_hypothesis(hyp.status, target_status):
            raise ValidationError(f"Invalid hypothesis transition {hyp.status} -> {target_status}")
        return

    if et in {EventType.HYPOTHESIS_WEAKENED, EventType.HYPOTHESIS_SUSPENDED, EventType.HYPOTHESIS_REJECTED}:
        hid = payload.get("hypothesis_id")
        if not hid or hid not in state.hypotheses:
            raise ValidationError(f"{et} requires existing hypothesis_id")
        return

    if et == EventType.EXPERIMENT_PROPOSED:
        for field in ("id", "unknown_id", "title"):
            if not payload.get(field):
                raise ValidationError(f"ExperimentProposed requires {field}")
        if payload["unknown_id"] not in state.unknowns:
            raise ValidationError("target Unknown does not exist")
        if payload["id"] in state.experiments:
            raise ValidationError("Experiment already exists")
        return

    if et == EventType.EXPERIMENT_APPROVED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("ExperimentApproved requires existing experiment_id")
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.APPROVED):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> APPROVED")
        return

    if et == EventType.EXPERIMENT_SCHEDULED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("ExperimentScheduled requires existing experiment_id")
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.SCHEDULED):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> SCHEDULED")
        return

    if et == EventType.EXPERIMENT_STARTED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("ExperimentStarted requires existing experiment_id")
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.RUNNING):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> RUNNING")
        return

    if et == EventType.EXPERIMENT_COMPLETED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("ExperimentCompleted requires existing experiment_id")
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.COMPLETED):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> COMPLETED")
        return

    if et == EventType.EVIDENCE_RECORDED:
        for field in ("id", "experiment_id", "observation"):
            if not payload.get(field):
                raise ValidationError(f"EvidenceRecorded requires {field}")
        eid = payload["experiment_id"]
        if eid not in state.experiments:
            raise ValidationError("EvidenceRecorded requires existing experiment")
        exp = state.experiments[eid]
        if exp.status not in {ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED}:
            raise ValidationError("Evidence requires experiment RUNNING or COMPLETED")
        if not payload.get("provenance"):
            raise ValidationError("EvidenceRecorded requires provenance")
        return

    if et == EventType.INTERPRETATION_SUBMITTED:
        for field in ("id", "evidence_id", "hypothesis_id", "outcome", "rationale"):
            if not payload.get(field):
                raise ValidationError(f"InterpretationSubmitted requires {field}")
        if payload["evidence_id"] not in state.evidence:
            raise ValidationError("evidence_id does not exist")
        if payload["hypothesis_id"] not in state.hypotheses:
            raise ValidationError("hypothesis_id does not exist")
        try:
            InterpretationOutcome(payload["outcome"])
        except ValueError as exc:
            raise ValidationError(f"Invalid interpretation outcome {payload['outcome']}") from exc
        return

    if et == EventType.ROOT_CAUSE_ACCEPTED:
        if not payload.get("hypothesis_id"):
            raise ValidationError("RootCauseAccepted requires hypothesis_id")
        if payload["hypothesis_id"] not in state.hypotheses:
            raise ValidationError("hypothesis_id does not exist")
        if not payload.get("rationale"):
            raise ValidationError("RootCauseAccepted requires rationale")
        return

    if et == EventType.PATCH_APPLIED:
        if not payload.get("experiment_id") or not payload.get("paths"):
            raise ValidationError("PatchApplied requires experiment_id and paths")
        return

    if et in {
        EventType.INVESTIGATION_ACTIVATED,
        EventType.INVESTIGATION_ESCALATED,
        EventType.INVESTIGATION_RESOLVED,
        EventType.INVESTIGATION_ABANDONED,
        EventType.INVESTIGATION_CLOSED,
        EventType.VALIDATION_FAILED,
        EventType.VERIFICATION_FAILED,
        EventType.IMPLEMENTATION_FAILED,
        EventType.EXPERIMENT_CANCELLED,
        EventType.EXPERIMENT_EXPIRED,
        EventType.INTERPRETATION_WITHDRAWN,
        EventType.UNKNOWN_REOPENED,
    }:
        return

    raise ValidationError(f"Unsupported event type {et}")


def apply_event(state: CaseState | None, event: DomainEvent) -> CaseState:
    """Apply a validated event; returns new Case State."""
    validate_event(state, event)
    et = event.event_type
    payload = event.payload

    if et == EventType.CASE_CREATED:
        new_state = CaseState(
            case_id=event.case_id,
            title=payload["title"],
            issue_path=payload.get("issue_path"),
            status=InvestigationStatus.CREATED,
            event_count=1,
            revision=1,
        )
        return new_state

    assert state is not None
    s = state.model_copy(deep=True)
    s.event_count += 1
    s.revision += 1

    if et == EventType.INVESTIGATION_ACTIVATED:
        s.status = InvestigationStatus.ACTIVE
    elif et == EventType.INVESTIGATION_ESCALATED:
        s.status = InvestigationStatus.ESCALATED
        s.decision_state["escalated"] = True
        s.decision_state["escalation_reason"] = payload.get("reason")
    elif et == EventType.INVESTIGATION_RESOLVED:
        s.status = InvestigationStatus.RESOLVED
    elif et == EventType.INVESTIGATION_ABANDONED:
        s.status = InvestigationStatus.ABANDONED
    elif et == EventType.INVESTIGATION_CLOSED:
        s.decision_state["closed"] = True
    elif et == EventType.UNKNOWN_DISCOVERED:
        unk = Unknown(
            id=payload["id"],
            title=payload["title"],
            description=payload.get("description", ""),
            priority=payload.get("priority", "HIGH"),
            status=UnknownStatus.ACTIVE,
            related_components=payload.get("related_components", []),
        )
        s.unknowns[unk.id] = unk
    elif et == EventType.UNKNOWN_RESOLVED:
        s.unknowns[payload["unknown_id"]].status = UnknownStatus.RESOLVED
    elif et == EventType.UNKNOWN_REOPENED:
        s.unknowns[payload["unknown_id"]].status = UnknownStatus.ACTIVE
    elif et == EventType.HYPOTHESIS_PROPOSED:
        hyp = Hypothesis(
            id=payload["id"],
            unknown_id=payload["unknown_id"],
            title=payload["title"],
            explanation=payload["explanation"],
            assumptions=payload.get("assumptions", []),
        )
        s.hypotheses[hyp.id] = hyp
    elif et == EventType.HYPOTHESIS_PROMOTED:
        s.hypotheses[payload["hypothesis_id"]].status = HypothesisStatus(payload["to_status"])
    elif et == EventType.HYPOTHESIS_WEAKENED:
        s.hypotheses[payload["hypothesis_id"]].status = HypothesisStatus.WEAKENED
    elif et == EventType.HYPOTHESIS_SUSPENDED:
        s.hypotheses[payload["hypothesis_id"]].status = HypothesisStatus.SUSPENDED
    elif et == EventType.HYPOTHESIS_REJECTED:
        s.hypotheses[payload["hypothesis_id"]].status = HypothesisStatus.REJECTED
    elif et == EventType.EXPERIMENT_PROPOSED:
        spec_data = payload.get("verification_spec")
        spec = VerificationSpec.model_validate(spec_data) if spec_data else None
        exp = Experiment(
            id=payload["id"],
            unknown_id=payload["unknown_id"],
            title=payload["title"],
            description=payload.get("description", ""),
            information_gain=payload.get("information_gain", "MEDIUM"),
            cost=payload.get("cost", "LOW"),
            affected_hypotheses=payload.get("affected_hypotheses", []),
            expected_observations=payload.get("expected_observations", []),
            verification_spec=spec,
            experiment_class=payload.get("experiment_class", "observational"),
            patch=payload.get("patch"),
        )
        s.experiments[exp.id] = exp
    elif et == EventType.EXPERIMENT_APPROVED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.APPROVED
    elif et == EventType.EXPERIMENT_SCHEDULED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.SCHEDULED
    elif et == EventType.EXPERIMENT_STARTED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.RUNNING
    elif et == EventType.EXPERIMENT_COMPLETED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.COMPLETED
    elif et == EventType.EXPERIMENT_CANCELLED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.CANCELLED
    elif et == EventType.EXPERIMENT_EXPIRED:
        s.experiments[payload["experiment_id"]].status = ExperimentStatus.EXPIRED
    elif et == EventType.EVIDENCE_RECORDED:
        ev = Evidence(
            id=payload["id"],
            experiment_id=payload["experiment_id"],
            observation=payload["observation"],
            category=payload.get("category", "Test Result"),
            provenance=payload.get("provenance", "verifier"),
            reproducibility=payload.get("reproducibility", "repeatable"),
            collection_method=payload.get("collection_method", "pytest"),
            reliability=payload.get("reliability", "HIGH"),
            attributes=payload.get("attributes", {}),
        )
        s.evidence[ev.id] = ev
    elif et == EventType.INTERPRETATION_SUBMITTED:
        interp = Interpretation(
            id=payload["id"],
            evidence_id=payload["evidence_id"],
            hypothesis_id=payload["hypothesis_id"],
            outcome=InterpretationOutcome(payload["outcome"]),
            rationale=payload["rationale"],
            producer=event.producer,
        )
        s.interpretations[interp.id] = interp
    elif et == EventType.ROOT_CAUSE_ACCEPTED:
        s.decision_state["root_cause_hypothesis_id"] = payload["hypothesis_id"]
        s.decision_state["root_cause_rationale"] = payload["rationale"]
        s.hypotheses[payload["hypothesis_id"]].status = HypothesisStatus.ACCEPTED
        s.status = InvestigationStatus.RESOLVED
    elif et == EventType.PATCH_APPLIED:
        s.decision_state.setdefault("patches", []).append(payload)
    elif et == EventType.VERIFICATION_FAILED:
        s.decision_state.setdefault("verification_failures", []).append(payload)
    elif et == EventType.VALIDATION_FAILED:
        s.decision_state.setdefault("validation_failures", []).append(payload)

    return s

from __future__ import annotations

from pathlib import Path
from typing import Any

from debugging_engine.domain.models import (
    AgentRole,
    CaseState,
    DomainEvent,
    EventType,
    Evidence,
    Experiment,
    ExperimentCost,
    ExperimentStatus,
    Hypothesis,
    HypothesisStatus,
    Interpretation,
    InterpretationOutcome,
    InvestigationMode,
    InvestigationStatus,
    ObjectionCategory,
    Unknown,
    UnknownStatus,
    VerificationSpec,
)
from debugging_engine.domain.transitions import (
    can_promote_hypothesis,
    can_transition_experiment,
    can_transition_unknown,
)
from debugging_engine.domain.policies import (
    INACTIVE_HYPOTHESIS_STATUSES,
    MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
)


class ValidationError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


def _is_intervention(exp: Experiment | dict[str, Any]) -> bool:
    if isinstance(exp, Experiment):
        return exp.experiment_class == "intervention" or bool(exp.patch)
    return exp.get("experiment_class") == "intervention" or bool(exp.get("patch"))


def _has_intervention_experiments(state: CaseState) -> bool:
    return any(_is_intervention(e) for e in state.experiments.values())


def _passed_intervention(state: CaseState) -> bool:
    return any(
        _is_intervention(e)
        and e.status == ExperimentStatus.COMPLETED
        and any(
            ev.experiment_id == e.id and ev.attributes.get("passed") is True
            for ev in state.evidence.values()
        )
        for e in state.experiments.values()
    )


def _rca_resolves_immediately(state: CaseState) -> bool:
    """Investigate always resolves on RCA; incident resolves when no interventions exist."""
    if state.mode == InvestigationMode.INVESTIGATE:
        return True
    if state.mode == InvestigationMode.PRODUCTION:
        return False
    return not _has_intervention_experiments(state)


def _risky_intervention(exp: Experiment) -> bool:
    return _is_intervention(exp) and exp.cost in {
        ExperimentCost.HIGH,
        ExperimentCost.CRITICAL,
    }


def validate_event(state: CaseState | None, event: DomainEvent) -> None:
    """Validate event against current Case State before append."""
    et = event.event_type
    payload = event.payload

    if et == EventType.CASE_CREATED:
        if state is not None and state.event_count > 0:
            raise ValidationError("Case already exists")
        if not payload.get("title"):
            raise ValidationError("CaseCreated requires title")
        mode = payload.get("mode", InvestigationMode.INCIDENT.value)
        try:
            InvestigationMode(mode)
        except ValueError as exc:
            raise ValidationError(
                f"Invalid investigation mode {mode}",
                {"allowed": [m.value for m in InvestigationMode]},
            ) from exc
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
        parent = payload.get("parent_unknown")
        if parent is not None:
            if parent not in state.unknowns:
                raise ValidationError("parent_unknown does not exist", {"parent_unknown": parent})
            if parent == payload["id"]:
                raise ValidationError("parent_unknown cannot reference self")
        return

    if et == EventType.UNKNOWN_RESOLVED:
        uid = payload.get("unknown_id")
        if not uid or uid not in state.unknowns:
            raise ValidationError("UnknownResolved requires existing unknown_id")
        unk = state.unknowns[uid]
        if not can_transition_unknown(unk.status, UnknownStatus.RESOLVED):
            raise ValidationError(f"Invalid unknown transition {unk.status} -> RESOLVED")
        return

    if et == EventType.UNKNOWN_PARTIALLY_RESOLVED:
        uid = payload.get("unknown_id")
        if not uid or uid not in state.unknowns:
            raise ValidationError("UnknownPartiallyResolved requires existing unknown_id")
        unk = state.unknowns[uid]
        if not can_transition_unknown(unk.status, UnknownStatus.PARTIALLY_RESOLVED):
            raise ValidationError(
                f"Invalid unknown transition {unk.status} -> PARTIALLY_RESOLVED"
            )
        if not payload.get("rationale"):
            raise ValidationError("UnknownPartiallyResolved requires rationale")
        return

    if et == EventType.HUMAN_RESPONSE_RECEIVED:
        if event.producer != AgentRole.HUMAN:
            raise ValidationError(
                "HumanResponseReceived requires producer Human",
                {"producer": event.producer},
            )
        if not payload.get("message"):
            raise ValidationError("HumanResponseReceived requires message")
        decision = payload.get("decision")
        approval_for = payload.get("approval_for")
        if decision is not None or approval_for is not None:
            if not approval_for:
                raise ValidationError(
                    "HumanResponseReceived decision requires approval_for experiment_id"
                )
            if approval_for not in state.experiments:
                raise ValidationError(
                    "HumanResponseReceived approval_for must be an existing experiment",
                    {"approval_for": approval_for},
                )
            if decision not in {"approve", "reject"}:
                raise ValidationError(
                    "HumanResponseReceived decision must be approve or reject",
                    {"decision": decision},
                )
        return

    if et == EventType.ORG_APPROVAL_RECEIVED:
        if event.producer != AgentRole.HUMAN:
            raise ValidationError(
                "OrgApprovalReceived requires producer Human",
                {"producer": event.producer},
            )
        if payload.get("approved") is not True:
            raise ValidationError("OrgApprovalReceived requires approved: true")
        if not payload.get("rationale") and not payload.get("message"):
            raise ValidationError("OrgApprovalReceived requires rationale or message")
        return

    if et == EventType.KNOWLEDGE_VALIDATED:
        if not payload.get("fingerprint") and not payload.get("knowledge_id"):
            raise ValidationError("KnowledgeValidated requires fingerprint or knowledge_id")
        return

    if et == EventType.HYPOTHESIS_PROPOSED:
        for field in ("id", "unknown_id", "title", "explanation"):
            if not payload.get(field):
                raise ValidationError(f"HypothesisProposed requires {field}")
        if payload["unknown_id"] not in state.unknowns:
            raise ValidationError("target Unknown does not exist")
        if payload["id"] in state.hypotheses:
            raise ValidationError("Hypothesis already exists")
        parent_id = payload.get("parent_id")
        if parent_id:
            if parent_id not in state.hypotheses:
                raise ValidationError("parent_id does not exist")
            parent = state.hypotheses[parent_id]
            if parent.unknown_id != payload["unknown_id"]:
                raise ValidationError("parent_id must belong to the same Unknown")
            if parent_id == payload["id"]:
                raise ValidationError("parent_id cannot reference self")
            # Reject cycles: walk ancestors.
            seen = {payload["id"]}
            cursor: str | None = parent_id
            while cursor is not None:
                if cursor in seen:
                    raise ValidationError("parent_id would create a cycle")
                seen.add(cursor)
                cursor = state.hypotheses[cursor].parent_id
        active = sum(
            1
            for h in state.hypotheses.values()
            if h.unknown_id == payload["unknown_id"]
            and h.status.value not in INACTIVE_HYPOTHESIS_STATUSES
        )
        if active >= MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN:
            raise ValidationError(
                "Hypothesis budget exceeded for Unknown",
                {
                    "unknown_id": payload["unknown_id"],
                    "active": active,
                    "max": MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
                },
            )
        if event.producer == AgentRole.ADVERSARY:
            cat = payload.get("objection_category")
            if not cat:
                raise ValidationError(
                    "Adversary HypothesisProposed requires objection_category",
                )
            try:
                ObjectionCategory(cat)
            except ValueError as exc:
                raise ValidationError(
                    f"Invalid objection_category {cat}",
                    {"allowed": [c.value for c in ObjectionCategory]},
                ) from exc
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
        patch = payload.get("patch")
        if patch is not None:
            if not isinstance(patch, dict):
                raise ValidationError("ExperimentProposed patch must be a mapping of path -> content")
            for rel in patch:
                if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                    raise ValidationError(
                        "ExperimentProposed patch paths must be relative and contained",
                        {"path": rel},
                    )
        if state.mode == InvestigationMode.INVESTIGATE and _is_intervention(payload):
            raise ValidationError(
                "investigate mode forbids intervention experiments and patches",
                {"mode": state.mode.value},
            )
        return

    if et == EventType.EXPERIMENT_APPROVED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("ExperimentApproved requires existing experiment_id")
        # Approval is Judge-only — Analyst/other roles must not self-approve.
        if event.producer != AgentRole.JUDGE:
            raise ValidationError(
                "ExperimentApproved requires producer Judge",
                {"producer": event.producer},
            )
        if payload.get("authority") != AgentRole.JUDGE:
            raise ValidationError(
                "ExperimentApproved requires authority Judge",
                {"authority": payload.get("authority")},
            )
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.APPROVED):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> APPROVED")
        if state.mode == InvestigationMode.INVESTIGATE and _is_intervention(exp):
            raise ValidationError(
                "investigate mode forbids approving intervention experiments",
                {"experiment_id": eid},
            )
        if state.mode == InvestigationMode.PRODUCTION and _risky_intervention(exp):
            approvals = state.decision_state.get("intervention_approvals") or {}
            if approvals.get(eid) != "approve":
                raise ValidationError(
                    "production mode requires Human approve for HIGH/CRITICAL interventions",
                    {
                        "experiment_id": eid,
                        "cost": exp.cost.value,
                        "hint": "Submit HumanResponseReceived with approval_for and decision=approve",
                    },
                )
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
        if event.producer == AgentRole.ADVERSARY:
            cat = payload.get("objection_category")
            if not cat:
                raise ValidationError(
                    "Adversary InterpretationSubmitted requires objection_category",
                )
            try:
                ObjectionCategory(cat)
            except ValueError as exc:
                raise ValidationError(
                    f"Invalid objection_category {cat}",
                    {"allowed": [c.value for c in ObjectionCategory]},
                ) from exc
        return

    if et == EventType.ROOT_CAUSE_ACCEPTED:
        if event.producer != AgentRole.JUDGE:
            raise ValidationError(
                "RootCauseAccepted requires producer Judge",
                {"producer": event.producer},
            )
        if payload.get("authority") != AgentRole.JUDGE:
            raise ValidationError(
                "RootCauseAccepted requires authority Judge",
                {"authority": payload.get("authority")},
            )
        hid = payload.get("hypothesis_id")
        if not hid:
            raise ValidationError("RootCauseAccepted requires hypothesis_id")
        if hid not in state.hypotheses:
            raise ValidationError("hypothesis_id does not exist")
        if not payload.get("rationale"):
            raise ValidationError("RootCauseAccepted requires rationale")

        supporting = [
            i
            for i in state.interpretations.values()
            if i.hypothesis_id == hid and i.outcome == InterpretationOutcome.SUPPORTS
        ]
        if not supporting:
            raise ValidationError(
                "RootCauseAccepted requires supporting interpretation",
                {"hypothesis_id": hid},
            )
        evidence_ids = {i.evidence_id for i in supporting}
        if not any(eid in state.evidence for eid in evidence_ids):
            raise ValidationError(
                "RootCauseAccepted requires evidence linked via supporting interpretation",
                {"hypothesis_id": hid},
            )

        # All terminal-experiment evidence must be interpreted before acceptance.
        interpreted = {i.evidence_id for i in state.interpretations.values()}
        terminal = {
            ExperimentStatus.COMPLETED,
            ExperimentStatus.FAILED,
        }
        for ev in state.evidence.values():
            exp = state.experiments.get(ev.experiment_id)
            if exp is not None and exp.status in terminal and ev.id not in interpreted:
                raise ValidationError(
                    "RootCauseAccepted requires all terminal evidence to be interpreted",
                    {"evidence_id": ev.id, "experiment_id": ev.experiment_id},
                )

        # At least one successful verification result must exist.
        has_passed = any(
            ev.attributes.get("passed") is True
            and state.experiments.get(ev.experiment_id) is not None
            and state.experiments[ev.experiment_id].status == ExperimentStatus.COMPLETED
            for ev in state.evidence.values()
        )
        if not has_passed:
            raise ValidationError(
                "RootCauseAccepted requires a successful verification (passed evidence)",
                {"hypothesis_id": hid},
            )

        # Competing active hypotheses must be disposed (rejected/suspended/accepted).
        active_competitors = [
            h
            for h in state.hypotheses.values()
            if h.id != hid and h.status.value not in INACTIVE_HYPOTHESIS_STATUSES
        ]
        if active_competitors:
            raise ValidationError(
                "RootCauseAccepted requires competing hypotheses to be rejected or suspended",
                {"active_competitors": [h.id for h in active_competitors]},
            )
        return

    if et == EventType.FIX_ACCEPTED:
        if event.producer != AgentRole.JUDGE:
            raise ValidationError(
                "FixAccepted requires producer Judge",
                {"producer": event.producer},
            )
        if payload.get("authority") != AgentRole.JUDGE:
            raise ValidationError(
                "FixAccepted requires authority Judge",
                {"authority": payload.get("authority")},
            )
        if not state.accepted_root_cause_id and not state.decision_state.get(
            "root_cause_hypothesis_id"
        ):
            raise ValidationError(
                "FixAccepted requires RootCauseAccepted first",
            )
        if not payload.get("rationale"):
            raise ValidationError("FixAccepted requires rationale")
        if not _passed_intervention(state):
            raise ValidationError(
                "FixAccepted requires a successful intervention experiment",
            )
        if state.mode == InvestigationMode.PRODUCTION and not state.decision_state.get(
            "org_approved"
        ):
            raise ValidationError(
                "production mode FixAccepted requires OrgApprovalReceived first",
                {"mode": state.mode.value},
            )
        return

    if et == EventType.PATCH_APPLIED:
        if event.producer not in {AgentRole.IMPLEMENTER, AgentRole.VERIFIER}:
            raise ValidationError(
                "PatchApplied requires producer Implementer (or Verifier when auto-applied)",
                {"producer": event.producer},
            )
        if not payload.get("experiment_id") or not payload.get("paths"):
            raise ValidationError("PatchApplied requires experiment_id and paths")
        eid = payload["experiment_id"]
        if eid not in state.experiments:
            raise ValidationError("PatchApplied requires existing experiment_id")
        # Path containment for declared patch paths (actual write checks happen in verify).
        for rel in payload.get("paths") or []:
            if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise ValidationError(
                    "PatchApplied paths must be relative and contained",
                    {"path": rel},
                )
        return

    if et == EventType.VERIFICATION_FAILED:
        eid = payload.get("experiment_id")
        if not eid or eid not in state.experiments:
            raise ValidationError("VerificationFailed requires existing experiment_id")
        exp = state.experiments[eid]
        if not can_transition_experiment(exp.status, ExperimentStatus.FAILED):
            raise ValidationError(f"Invalid experiment transition {exp.status} -> FAILED")
        return

    if et in {
        EventType.INVESTIGATION_ACTIVATED,
        EventType.INVESTIGATION_ESCALATED,
        EventType.INVESTIGATION_RESOLVED,
        EventType.INVESTIGATION_ABANDONED,
        EventType.INVESTIGATION_CLOSED,
        EventType.VALIDATION_FAILED,
        EventType.IMPLEMENTATION_FAILED,
        EventType.EXPERIMENT_CANCELLED,
        EventType.EXPERIMENT_EXPIRED,
        EventType.INTERPRETATION_WITHDRAWN,
        EventType.UNKNOWN_REOPENED,
        EventType.KNOWLEDGE_VALIDATED,
    }:
        return

    raise ValidationError(f"Unsupported event type {et}")


def apply_event(state: CaseState | None, event: DomainEvent) -> CaseState:
    """Apply a validated event; returns new Case State."""
    validate_event(state, event)
    et = event.event_type
    payload = event.payload

    if et == EventType.CASE_CREATED:
        mode_raw = payload.get("mode", InvestigationMode.INCIDENT.value)
        new_state = CaseState(
            case_id=event.case_id,
            title=payload["title"],
            issue_path=payload.get("issue_path"),
            mode=InvestigationMode(mode_raw),
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
        parent = payload.get("parent_unknown")
        unk = Unknown(
            id=payload["id"],
            title=payload["title"],
            description=payload.get("description", ""),
            priority=payload.get("priority", "HIGH"),
            status=UnknownStatus.ACTIVE,
            related_components=payload.get("related_components", []),
            parent_unknown=parent,
            revision=1,
        )
        s.unknowns[unk.id] = unk
        if parent is not None and parent in s.unknowns:
            parent_unk = s.unknowns[parent]
            if unk.id not in parent_unk.child_unknowns:
                parent_unk.child_unknowns = [*parent_unk.child_unknowns, unk.id]
            parent_unk.revision += 1
    elif et == EventType.UNKNOWN_RESOLVED:
        unk = s.unknowns[payload["unknown_id"]]
        unk.status = UnknownStatus.RESOLVED
        unk.revision += 1
    elif et == EventType.UNKNOWN_PARTIALLY_RESOLVED:
        unk = s.unknowns[payload["unknown_id"]]
        unk.status = UnknownStatus.PARTIALLY_RESOLVED
        unk.revision += 1
        s.decision_state["partial_resolution"] = {
            "unknown_id": payload["unknown_id"],
            "rationale": payload.get("rationale"),
        }
    elif et == EventType.UNKNOWN_REOPENED:
        unk = s.unknowns[payload["unknown_id"]]
        unk.status = UnknownStatus.ACTIVE
        unk.revision += 1
    elif et == EventType.HYPOTHESIS_PROPOSED:
        hyp = Hypothesis(
            id=payload["id"],
            unknown_id=payload["unknown_id"],
            title=payload["title"],
            explanation=payload["explanation"],
            assumptions=payload.get("assumptions", []),
            parent_id=payload.get("parent_id"),
            objection_category=payload.get("objection_category"),
            revision=1,
        )
        s.hypotheses[hyp.id] = hyp
        if event.producer == AgentRole.ADVERSARY:
            s.decision_state["adversary_challenged"] = True
    elif et == EventType.HYPOTHESIS_PROMOTED:
        hyp = s.hypotheses[payload["hypothesis_id"]]
        hyp.status = HypothesisStatus(payload["to_status"])
        hyp.revision += 1
    elif et == EventType.HYPOTHESIS_WEAKENED:
        hyp = s.hypotheses[payload["hypothesis_id"]]
        hyp.status = HypothesisStatus.WEAKENED
        hyp.revision += 1
    elif et == EventType.HYPOTHESIS_SUSPENDED:
        hyp = s.hypotheses[payload["hypothesis_id"]]
        hyp.status = HypothesisStatus.SUSPENDED
        hyp.revision += 1
    elif et == EventType.HYPOTHESIS_REJECTED:
        # Cascade: rejecting a parent rejects all descendants (deterministic on replay).
        rejected_root = payload["hypothesis_id"]
        s.hypotheses[rejected_root].status = HypothesisStatus.REJECTED
        s.hypotheses[rejected_root].revision += 1
        changed = True
        while changed:
            changed = False
            for hyp in s.hypotheses.values():
                if (
                    hyp.parent_id is not None
                    and s.hypotheses[hyp.parent_id].status == HypothesisStatus.REJECTED
                    and hyp.status != HypothesisStatus.REJECTED
                ):
                    hyp.status = HypothesisStatus.REJECTED
                    hyp.revision += 1
                    changed = True
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
            revision=1,
        )
        s.experiments[exp.id] = exp
        if event.producer == AgentRole.ADVERSARY:
            s.decision_state["adversary_challenged"] = True
    elif et == EventType.EXPERIMENT_APPROVED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.APPROVED
        exp.revision += 1
    elif et == EventType.EXPERIMENT_SCHEDULED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.SCHEDULED
        exp.revision += 1
    elif et == EventType.EXPERIMENT_STARTED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.RUNNING
        exp.revision += 1
    elif et == EventType.EXPERIMENT_COMPLETED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.COMPLETED
        exp.revision += 1
    elif et == EventType.EXPERIMENT_CANCELLED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.CANCELLED
        exp.revision += 1
    elif et == EventType.EXPERIMENT_EXPIRED:
        exp = s.experiments[payload["experiment_id"]]
        exp.status = ExperimentStatus.EXPIRED
        exp.revision += 1
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
            revision=1,
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
            objection_category=payload.get("objection_category"),
            revision=1,
        )
        s.interpretations[interp.id] = interp
        hyp = s.hypotheses[interp.hypothesis_id]
        if (
            interp.outcome == InterpretationOutcome.SUPPORTS
            and hyp.status == HypothesisStatus.PROPOSED
        ):
            hyp.status = HypothesisStatus.PLAUSIBLE
            hyp.revision += 1
        elif (
            interp.outcome == InterpretationOutcome.SUPPORTS
            and hyp.status == HypothesisStatus.PLAUSIBLE
        ):
            hyp.status = HypothesisStatus.SUPPORTED
            hyp.revision += 1
        elif (
            interp.outcome == InterpretationOutcome.SUPPORTS
            and hyp.status == HypothesisStatus.SUPPORTED
        ):
            hyp.status = HypothesisStatus.STRONGLY_SUPPORTED
            hyp.revision += 1
        elif (
            interp.outcome == InterpretationOutcome.WEAKENS
            and hyp.status
            in {
                HypothesisStatus.PROPOSED,
                HypothesisStatus.PLAUSIBLE,
                HypothesisStatus.SUPPORTED,
                HypothesisStatus.STRONGLY_SUPPORTED,
            }
        ):
            hyp.status = HypothesisStatus.WEAKENED
            hyp.revision += 1
    elif et == EventType.HUMAN_RESPONSE_RECEIVED:
        responses = list(s.decision_state.get("human_responses", []))
        responses.append(
            {
                "message": payload.get("message"),
                "timestamp": event.timestamp,
                "approval_for": payload.get("approval_for"),
                "decision": payload.get("decision"),
                "attributes": payload.get("attributes", {}),
            }
        )
        s.decision_state["human_responses"] = responses
        approval_for = payload.get("approval_for")
        decision = payload.get("decision")
        if approval_for and decision:
            approvals = dict(s.decision_state.get("intervention_approvals") or {})
            approvals[approval_for] = decision
            s.decision_state["intervention_approvals"] = approvals
    elif et == EventType.ORG_APPROVAL_RECEIVED:
        s.decision_state["org_approved"] = True
        s.decision_state["org_approval_rationale"] = payload.get("rationale") or payload.get(
            "message"
        )
    elif et == EventType.KNOWLEDGE_VALIDATED:
        items = list(s.decision_state.get("knowledge", []))
        items.append(
            {
                "fingerprint": payload.get("fingerprint"),
                "knowledge_id": payload.get("knowledge_id"),
                "timestamp": event.timestamp,
            }
        )
        s.decision_state["knowledge"] = items
    elif et == EventType.ROOT_CAUSE_ACCEPTED:
        s.decision_state["root_cause_hypothesis_id"] = payload["hypothesis_id"]
        s.decision_state["root_cause_rationale"] = payload["rationale"]
        s.accepted_root_cause_id = payload["hypothesis_id"]
        hyp = s.hypotheses[payload["hypothesis_id"]]
        hyp.status = HypothesisStatus.ACCEPTED
        hyp.revision += 1
        if _rca_resolves_immediately(s):
            s.status = InvestigationStatus.RESOLVED
            s.decision_state["fix_accepted"] = False
        else:
            s.decision_state["awaiting_fix"] = True
    elif et == EventType.FIX_ACCEPTED:
        s.decision_state["fix_accepted"] = True
        s.decision_state["fix_accepted_rationale"] = payload.get("rationale")
        s.decision_state.pop("awaiting_fix", None)
        s.status = InvestigationStatus.RESOLVED
    elif et == EventType.PATCH_APPLIED:
        s.decision_state.setdefault("patches", []).append(payload)
    elif et == EventType.VERIFICATION_FAILED:
        s.decision_state.setdefault("verification_failures", []).append(payload)
        eid = payload.get("experiment_id")
        if eid and eid in s.experiments:
            s.experiments[eid].status = ExperimentStatus.FAILED
            s.experiments[eid].revision += 1
    elif et == EventType.VALIDATION_FAILED:
        s.decision_state.setdefault("validation_failures", []).append(payload)

    return s

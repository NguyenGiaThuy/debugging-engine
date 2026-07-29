from __future__ import annotations

from pydantic import BaseModel, Field

from smadw.domain.models import (
    AgentRole,
    CaseState,
    EventType,
    ExperimentCost,
    ExperimentStatus,
    HypothesisStatus,
    InformationGain,
    InvestigationStatus,
)


class Task(BaseModel):
    """Handoff from Judge to an external coding agent (or stub)."""

    case_id: str
    role: AgentRole
    objective: str
    allowed_event_types: list[str]
    projection: dict = Field(default_factory=dict)
    hints: list[str] = Field(default_factory=list)
    done: bool = False
    terminal_status: str | None = None


GAIN_RANK = {
    InformationGain.HIGH: 3,
    InformationGain.MEDIUM: 2,
    InformationGain.LOW: 1,
    InformationGain.MINIMAL: 0,
}

COST_RANK = {
    ExperimentCost.LOW: 0,
    ExperimentCost.MEDIUM: 1,
    ExperimentCost.HIGH: 2,
    ExperimentCost.CRITICAL: 3,
}


def _slice_for_role(state: CaseState, role: AgentRole) -> dict:
    base = {
        "case_id": state.case_id,
        "title": state.title,
        "status": state.status.value,
        "issue_path": state.issue_path,
        "unknowns": {k: v.model_dump(mode="json") for k, v in state.unknowns.items()},
        "hypotheses": {k: v.model_dump(mode="json") for k, v in state.hypotheses.items()},
        "experiments": {k: v.model_dump(mode="json") for k, v in state.experiments.items()},
        "evidence": {k: v.model_dump(mode="json") for k, v in state.evidence.items()},
        "interpretations": {k: v.model_dump(mode="json") for k, v in state.interpretations.items()},
        "decision_state": state.decision_state,
    }
    if role == AgentRole.ANALYST:
        return {
            "unknowns": base["unknowns"],
            "hypotheses": base["hypotheses"],
            "evidence": base["evidence"],
            "interpretations": base["interpretations"],
            "issue_path": base["issue_path"],
        }
    if role == AgentRole.ADVERSARY:
        return {
            "hypotheses": base["hypotheses"],
            "evidence": base["evidence"],
            "interpretations": base["interpretations"],
        }
    if role == AgentRole.IMPLEMENTER:
        return {
            "experiments": {
                k: v
                for k, v in base["experiments"].items()
                if v["status"] in {"APPROVED", "SCHEDULED"}
            },
            "issue_path": base["issue_path"],
        }
    return base


def schedule_next_task(state: CaseState) -> Task:
    """Pure Judge policy: pick next role/task without technical reasoning."""
    if state.status in {
        InvestigationStatus.RESOLVED,
        InvestigationStatus.ABANDONED,
        InvestigationStatus.ESCALATED,
    }:
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective="Investigation is terminal; no further tasks.",
            allowed_event_types=[],
            projection=_slice_for_role(state, AgentRole.JUDGE),
            done=True,
            terminal_status=state.status.value,
        )

    if state.decision_state.get("root_cause_hypothesis_id"):
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective="Root cause already accepted.",
            allowed_event_types=[],
            projection=_slice_for_role(state, AgentRole.JUDGE),
            done=True,
            terminal_status=InvestigationStatus.RESOLVED.value,
        )

    # Need hypotheses?
    if not state.hypotheses:
        return Task(
            case_id=state.case_id,
            role=AgentRole.ANALYST,
            objective="Propose hypotheses and at least one discriminating experiment for open unknowns.",
            allowed_event_types=[
                EventType.HYPOTHESIS_PROPOSED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection=_slice_for_role(state, AgentRole.ANALYST),
            hints=["Declare assumptions explicitly.", "Estimate information_gain and cost qualitatively."],
        )

    # Need adversary challenge if only one hypothesis and no interpretations yet
    if len(state.hypotheses) == 1 and not any(
        h.title.lower().find("logging") >= 0 or "alternative" in h.explanation.lower()
        for h in state.hypotheses.values()
    ):
        # Soft: if adversary hasn't added a competing hypothesis
        pass

    competing = [h for h in state.hypotheses.values() if h.status not in {HypothesisStatus.REJECTED, HypothesisStatus.SUSPENDED}]
    if len(competing) < 2 and not state.evidence:
        return Task(
            case_id=state.case_id,
            role=AgentRole.ADVERSARY,
            objective="Challenge the current explanation; propose an alternative hypothesis and/or discriminating experiment.",
            allowed_event_types=[
                EventType.HYPOTHESIS_PROPOSED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection=_slice_for_role(state, AgentRole.ADVERSARY),
            hints=["Objections must use a defined category.", "Prefer experiments that discriminate."],
        )

    # Approve / schedule best proposed experiment
    proposed = [e for e in state.experiments.values() if e.status == ExperimentStatus.PROPOSED]
    if proposed:
        proposed.sort(key=lambda e: (-GAIN_RANK[e.information_gain], COST_RANK[e.cost]))
        best = proposed[0]
        # Reject minimal+critical
        if best.information_gain == InformationGain.MINIMAL and best.cost == ExperimentCost.CRITICAL:
            return Task(
                case_id=state.case_id,
                role=AgentRole.ANALYST,
                objective="Previous experiment has MINIMAL gain and CRITICAL cost; propose a better experiment.",
                allowed_event_types=[EventType.EXPERIMENT_PROPOSED.value],
                projection=_slice_for_role(state, AgentRole.ANALYST),
            )
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective=f"Approve and prepare experiment '{best.title}' ({best.id}).",
            allowed_event_types=[
                EventType.EXPERIMENT_APPROVED.value,
                EventType.EXPERIMENT_SCHEDULED.value,
            ],
            projection={
                "recommended_experiment_id": best.id,
                "experiment": best.model_dump(mode="json"),
            },
            hints=["Submit ExperimentApproved then optionally ExperimentScheduled."],
        )

    # Ready to verify?
    runnable = [
        e
        for e in state.experiments.values()
        if e.status in {ExperimentStatus.APPROVED, ExperimentStatus.SCHEDULED, ExperimentStatus.RUNNING}
    ]
    if runnable:
        runnable.sort(key=lambda e: (-GAIN_RANK[e.information_gain], COST_RANK[e.cost]))
        exp = runnable[0]
        return Task(
            case_id=state.case_id,
            role=AgentRole.VERIFIER,
            objective=f"Run verification for experiment '{exp.title}' ({exp.id}) via `smadw verify`.",
            allowed_event_types=[
                EventType.EXPERIMENT_STARTED.value,
                EventType.EVIDENCE_RECORDED.value,
                EventType.EXPERIMENT_COMPLETED.value,
                EventType.VERIFICATION_FAILED.value,
                EventType.PATCH_APPLIED.value,
            ],
            projection={"experiment_id": exp.id, "experiment": exp.model_dump(mode="json")},
            hints=["Prefer `smadw verify <case-id> <experiment-id>` rather than hand-writing evidence."],
        )

    # Interpret completed experiments without interpretations
    completed = [e for e in state.experiments.values() if e.status == ExperimentStatus.COMPLETED]
    interpreted_evidence = {i.evidence_id for i in state.interpretations.values()}
    for exp in completed:
        related = [ev for ev in state.evidence.values() if ev.experiment_id == exp.id]
        pending = [ev for ev in related if ev.id not in interpreted_evidence]
        if pending:
            return Task(
                case_id=state.case_id,
                role=AgentRole.ANALYST,
                objective="Submit interpretations linking new evidence to hypotheses.",
                allowed_event_types=[EventType.INTERPRETATION_SUBMITTED.value],
                projection={
                    "evidence": {e.id: e.model_dump(mode="json") for e in pending},
                    "hypotheses": {k: v.model_dump(mode="json") for k, v in state.hypotheses.items()},
                },
            )

    # Adversary competing interpretation if only one interpretation exists for latest evidence
    if state.evidence and len(state.interpretations) == 1:
        return Task(
            case_id=state.case_id,
            role=AgentRole.ADVERSARY,
            objective="Submit a competing interpretation of the latest evidence, or concede sufficiency.",
            allowed_event_types=[
                EventType.INTERPRETATION_SUBMITTED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection=_slice_for_role(state, AgentRole.ADVERSARY),
        )

    # Enough to accept root cause?
    supported = [
        h
        for h in state.hypotheses.values()
        if h.status in {HypothesisStatus.SUPPORTED, HypothesisStatus.STRONGLY_SUPPORTED, HypothesisStatus.PLAUSIBLE}
        and any(
            i.hypothesis_id == h.id and i.outcome.value == "SUPPORTS" for i in state.interpretations.values()
        )
    ]
    if supported and state.evidence:
        # Prefer hypothesis with SUPPORTS and passed tests
        best = supported[0]
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective="Evidence may be sufficient. Accept root cause or request another discriminating experiment.",
            allowed_event_types=[
                EventType.ROOT_CAUSE_ACCEPTED.value,
                EventType.UNKNOWN_RESOLVED.value,
                EventType.INVESTIGATION_ESCALATED.value,
                EventType.HYPOTHESIS_REJECTED.value,
                EventType.HYPOTHESIS_SUSPENDED.value,
            ],
            projection={
                "candidate_hypothesis_id": best.id,
                "hypotheses": {k: v.model_dump(mode="json") for k, v in state.hypotheses.items()},
                "interpretations": {k: v.model_dump(mode="json") for k, v in state.interpretations.items()},
            },
        )

    # Starvation recovery
    return Task(
        case_id=state.case_id,
        role=AgentRole.ANALYST,
        objective="Investigation stalled. Propose new experiments or escalate.",
        allowed_event_types=[
            EventType.EXPERIMENT_PROPOSED.value,
            EventType.HYPOTHESIS_PROPOSED.value,
            EventType.INVESTIGATION_ESCALATED.value,
        ],
        projection=_slice_for_role(state, AgentRole.ANALYST),
        hints=["Starvation policy: waiting indefinitely is prohibited."],
    )

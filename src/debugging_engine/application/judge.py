from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from debugging_engine.domain.models import (
    AgentRole,
    CaseState,
    EventType,
    ExperimentCost,
    ExperimentStatus,
    HypothesisStatus,
    InformationGain,
    InterpretationOutcome,
    InvestigationStatus,
)
from debugging_engine.domain.policies import (
    INACTIVE_HYPOTHESIS_STATUSES,
    MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN,
    MAX_PROJECTION_FIELD_CHARS,
    STALL_CYCLES_BEFORE_ESCALATION,
)

# Shown on every Task so coding agents cannot silently act as Judge/Verifier/etc.
ANNOUNCE_HANDOFF_HINT = (
    "Announce this handoff in chat as `**Role: <role>** — <objective>` "
    "before any submit/verify/patch. Silent role turns are forbidden."
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


def _short(text: str, limit: int = MAX_PROJECTION_FIELD_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _hyp_summary(state: CaseState) -> list[dict[str, Any]]:
    return [
        {
            "id": h.id,
            "unknown_id": h.unknown_id,
            "title": _short(h.title),
            "status": h.status.value,
        }
        for h in state.hypotheses.values()
    ]


def _unk_summary(state: CaseState) -> list[dict[str, Any]]:
    return [
        {
            "id": u.id,
            "title": _short(u.title),
            "status": u.status.value,
            "priority": u.priority,
        }
        for u in state.unknowns.values()
    ]


def _exp_summary(state: CaseState, *, statuses: set[str] | None = None) -> list[dict[str, Any]]:
    rows = []
    for e in state.experiments.values():
        if statuses and e.status.value not in statuses:
            continue
        rows.append(
            {
                "id": e.id,
                "title": _short(e.title),
                "status": e.status.value,
                "information_gain": e.information_gain.value,
                "cost": e.cost.value,
                "unknown_id": e.unknown_id,
                "has_patch": bool(e.patch),
                "has_verification_spec": e.verification_spec is not None,
            }
        )
    return rows


def _ev_summary(state: CaseState) -> list[dict[str, Any]]:
    return [
        {
            "id": e.id,
            "experiment_id": e.experiment_id,
            "observation": _short(e.observation),
            "passed": e.attributes.get("passed"),
            "exit_code": e.attributes.get("exit_code"),
        }
        for e in state.evidence.values()
    ]


def _interp_summary(state: CaseState) -> list[dict[str, Any]]:
    return [
        {
            "id": i.id,
            "evidence_id": i.evidence_id,
            "hypothesis_id": i.hypothesis_id,
            "outcome": i.outcome.value,
            "rationale": _short(i.rationale),
            "producer": i.producer,
        }
        for i in state.interpretations.values()
    ]


def _metrics_summary(state: CaseState) -> dict[str, Any]:
    return {
        "event_count": state.event_count,
        "revision": state.revision,
        "unknowns": len(state.unknowns),
        "hypotheses": len(state.hypotheses),
        "experiments": len(state.experiments),
        "evidence": len(state.evidence),
        "interpretations": len(state.interpretations),
        "scheduling_cycles": state.decision_state.get("scheduling_cycles", 0),
        "stall_cycles": state.decision_state.get("stall_cycles", 0),
        "last_progress_revision": state.decision_state.get("last_progress_revision"),
    }


def _slice_for_role(state: CaseState, role: AgentRole) -> dict:
    """ADR 0001 — role-minimal summaries, not full registries."""
    base_meta = {
        "case_id": state.case_id,
        "title": _short(state.title),
        "status": state.status.value,
        "issue_path": state.issue_path,
        "metrics": _metrics_summary(state),
    }
    if role == AgentRole.ANALYST:
        return {
            **base_meta,
            "unknowns": _unk_summary(state),
            "hypotheses": _hyp_summary(state),
            "evidence": _ev_summary(state),
            "interpretations": _interp_summary(state),
        }
    if role == AgentRole.ADVERSARY:
        return {
            **base_meta,
            "hypotheses": _hyp_summary(state),
            "evidence": _ev_summary(state),
            "interpretations": _interp_summary(state),
        }
    if role == AgentRole.IMPLEMENTER:
        return {
            **base_meta,
            "experiments": _exp_summary(state, statuses={"APPROVED", "SCHEDULED"}),
        }
    if role == AgentRole.VERIFIER:
        return {
            **base_meta,
            "experiments": _exp_summary(
                state, statuses={"APPROVED", "SCHEDULED", "RUNNING"}
            ),
        }
    return {
        **base_meta,
        "unknowns": _unk_summary(state),
        "hypotheses": _hyp_summary(state),
        "experiments": _exp_summary(state),
        "decision_keys": list(state.decision_state.keys()),
    }


def active_hypothesis_count(state: CaseState, unknown_id: str) -> int:
    return sum(
        1
        for h in state.hypotheses.values()
        if h.unknown_id == unknown_id and h.status.value not in INACTIVE_HYPOTHESIS_STATUSES
    )


def budget_remaining(state: CaseState, unknown_id: str) -> int:
    return max(0, MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN - active_hypothesis_count(state, unknown_id))


def unrebutted_supports_evidence_ids(state: CaseState) -> list[str]:
    """Evidence with SUPPORTS but no Adversary interpretation yet.

    Used to re-engage the Adversary after new results without infinite debate:
    each evidence id is challenged at most once by the Adversary.
    """
    needing: list[str] = []
    for ev in state.evidence.values():
        interps = [i for i in state.interpretations.values() if i.evidence_id == ev.id]
        if not interps:
            continue
        if any(i.producer == AgentRole.ADVERSARY for i in interps):
            continue
        if any(i.outcome == InterpretationOutcome.SUPPORTS for i in interps):
            needing.append(ev.id)
    return needing


def _adversary_rebuttal_task(state: CaseState, evidence_ids: list[str]) -> Task:
    return Task(
        case_id=state.case_id,
        role=AgentRole.ADVERSARY,
        objective=(
            "New supporting evidence lacks an Adversary rebuttal. "
            "Submit a competing interpretation, weaken/support with rationale, "
            "or propose a discriminating experiment."
        ),
        allowed_event_types=[
            EventType.INTERPRETATION_SUBMITTED.value,
            EventType.EXPERIMENT_PROPOSED.value,
            EventType.HYPOTHESIS_PROPOSED.value,
            EventType.HYPOTHESIS_SUSPENDED.value,
        ],
        projection={
            **_slice_for_role(state, AgentRole.ADVERSARY),
            "unrebutted_evidence_ids": evidence_ids,
        },
        hints=[
            ANNOUNCE_HANDOFF_HINT,
            "Announce this Adversary handoff in chat before challenging.",
            "Object using a defined category, or concede with an explicit interpretation.",
        ],
    )


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

    stall = int(state.decision_state.get("stall_cycles", 0))
    if stall >= STALL_CYCLES_BEFORE_ESCALATION:
        human_responses = state.decision_state.get("human_responses") or []
        if not human_responses:
            return Task(
                case_id=state.case_id,
                role=AgentRole.HUMAN,
                objective=(
                    f"No investigation progress for {stall} scheduling cycles. "
                    "Provide guidance or constraints; Judge may still escalate."
                ),
                allowed_event_types=[
                    EventType.HUMAN_RESPONSE_RECEIVED.value,
                    EventType.INVESTIGATION_ESCALATED.value,
                ],
                projection={
                    **_slice_for_role(state, AgentRole.JUDGE),
                    "stall_cycles": stall,
                    "threshold": STALL_CYCLES_BEFORE_ESCALATION,
                },
                hints=[
                    ANNOUNCE_HANDOFF_HINT,
                    "Submit HumanResponseReceived as producer Human.",
                    "Waiting indefinitely is prohibited (Part IV starvation policy).",
                ],
            )
        return Task(
            case_id=state.case_id,
            role=AgentRole.JUDGE,
            objective=(
                f"No investigation progress for {stall} scheduling cycles. "
                "Escalate or propose a discriminating HIGH/LOW-cost experiment."
            ),
            allowed_event_types=[
                EventType.INVESTIGATION_ESCALATED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection={
                **_slice_for_role(state, AgentRole.JUDGE),
                "stall_cycles": stall,
                "threshold": STALL_CYCLES_BEFORE_ESCALATION,
            },
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Waiting indefinitely is prohibited (Part IV starvation policy).",
            ],
        )

    # Need hypotheses?
    if not state.hypotheses:
        return Task(
            case_id=state.case_id,
            role=AgentRole.ANALYST,
            objective=(
                "Propose hypotheses and ExperimentProposed events for open unknowns. "
                "Do not approve, verify, or implement — call next after submit."
            ),
            allowed_event_types=[
                EventType.HYPOTHESIS_PROPOSED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection=_slice_for_role(state, AgentRole.ANALYST),
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Declare assumptions explicitly.",
                "Estimate information_gain and cost qualitatively.",
                f"Active hypothesis budget per Unknown: {MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN}.",
                "Propose experiments as events only; running verify/patches requires Judge approval and role handoffs.",
            ],
        )

    # Run already-approved experiments first so Verifier/Implementer are not starved.
    runnable = [
        e
        for e in state.experiments.values()
        if e.status in {ExperimentStatus.APPROVED, ExperimentStatus.SCHEDULED, ExperimentStatus.RUNNING}
    ]
    if runnable:
        runnable.sort(key=lambda e: (-GAIN_RANK[e.information_gain], COST_RANK[e.cost]))
        exp = runnable[0]
        applied_ids = {
            p.get("experiment_id")
            for p in state.decision_state.get("patches", [])
            if isinstance(p, dict)
        }
        if exp.patch and exp.id not in applied_ids:
            return Task(
                case_id=state.case_id,
                role=AgentRole.IMPLEMENTER,
                objective=(
                    f"Materialize the approved patch for experiment '{exp.title}' ({exp.id}), "
                    "then submit PatchApplied."
                ),
                allowed_event_types=[
                    EventType.PATCH_APPLIED.value,
                    EventType.IMPLEMENTATION_FAILED.value,
                ],
                projection={
                    "experiment_id": exp.id,
                    "experiment": {
                        "id": exp.id,
                        "title": _short(exp.title),
                        "status": exp.status.value,
                        "has_patch": True,
                        "patch_paths": list(exp.patch.keys()),
                    },
                    "metrics": _metrics_summary(state),
                },
                hints=[
                    ANNOUNCE_HANDOFF_HINT,
                    "Announce this Implementer handoff in chat before writing files.",
                    "Write patch files under the repo root exactly as specified.",
                    "After PatchApplied, the next task should be Verifier.",
                ],
            )
        return Task(
            case_id=state.case_id,
            role=AgentRole.VERIFIER,
            objective=f"Run verification for experiment '{exp.title}' ({exp.id}) via `debugging-engine verify`.",
            allowed_event_types=[
                EventType.EXPERIMENT_STARTED.value,
                EventType.EVIDENCE_RECORDED.value,
                EventType.EXPERIMENT_COMPLETED.value,
                EventType.VERIFICATION_FAILED.value,
                EventType.PATCH_APPLIED.value,
            ],
            projection={
                "experiment_id": exp.id,
                "experiment": {
                    "id": exp.id,
                    "title": _short(exp.title),
                    "status": exp.status.value,
                    "has_patch": bool(exp.patch),
                },
                "metrics": _metrics_summary(state),
            },
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Announce this Verifier handoff in chat before running verify.",
                "Prefer `debugging-engine verify <case-id> <experiment-id>` rather than hand-writing evidence.",
            ],
        )

    # Dialectic before approving: Adversary must challenge when evidence is absent
    # and no Adversary turn has run yet (single-hyp OR multi-hyp batch with proposals).
    competing = [
        h
        for h in state.hypotheses.values()
        if h.status not in {HypothesisStatus.REJECTED, HypothesisStatus.SUSPENDED}
    ]
    adversary_challenged = bool(state.decision_state.get("adversary_challenged"))
    proposed_pending = [
        e for e in state.experiments.values() if e.status == ExperimentStatus.PROPOSED
    ]
    if not state.evidence and not adversary_challenged and (
        len(competing) < 2 or proposed_pending
    ):
        unk_id = next(iter(state.unknowns))
        if budget_remaining(state, unk_id) == 0 and len(competing) < 2:
            return Task(
                case_id=state.case_id,
                role=AgentRole.ANALYST,
                objective="Hypothesis budget exhausted. Propose a discriminating experiment instead.",
                allowed_event_types=[EventType.EXPERIMENT_PROPOSED.value],
                projection=_slice_for_role(state, AgentRole.ANALYST),
            )
        return Task(
            case_id=state.case_id,
            role=AgentRole.ADVERSARY,
            objective=(
                "Challenge the current explanation before Judge approval; "
                "propose an alternative hypothesis and/or discriminating experiment."
            ),
            allowed_event_types=[
                EventType.HYPOTHESIS_PROPOSED.value,
                EventType.EXPERIMENT_PROPOSED.value,
            ],
            projection={
                **_slice_for_role(state, AgentRole.ADVERSARY),
                "budget_remaining": budget_remaining(state, unk_id),
            },
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Announce this Adversary handoff in chat before challenging.",
                "Objections must use a defined category.",
                "Prefer experiments that discriminate.",
                "Judge will not approve proposed experiments until this challenge runs.",
            ],
        )

    proposed = [e for e in state.experiments.values() if e.status == ExperimentStatus.PROPOSED]
    if proposed:
        unrebutted = unrebutted_supports_evidence_ids(state)
        if unrebutted:
            return _adversary_rebuttal_task(state, unrebutted)
        proposed.sort(key=lambda e: (-GAIN_RANK[e.information_gain], COST_RANK[e.cost]))
        best = proposed[0]
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
                "experiment": {
                    "id": best.id,
                    "title": _short(best.title),
                    "information_gain": best.information_gain.value,
                    "cost": best.cost.value,
                    "status": best.status.value,
                },
                "metrics": _metrics_summary(state),
            },
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Submit ExperimentApproved then optionally ExperimentScheduled.",
            ],
        )

    completed = [
        e
        for e in state.experiments.values()
        if e.status in {ExperimentStatus.COMPLETED, ExperimentStatus.FAILED}
    ]
    interpreted_evidence = {i.evidence_id for i in state.interpretations.values()}
    for exp in completed:
        related = [ev for ev in state.evidence.values() if ev.experiment_id == exp.id]
        pending = [ev for ev in related if ev.id not in interpreted_evidence]
        if pending:
            return Task(
                case_id=state.case_id,
                role=AgentRole.ANALYST,
                objective="Submit interpretations linking new evidence to hypotheses.",
                allowed_event_types=[
                    EventType.INTERPRETATION_SUBMITTED.value,
                    EventType.EXPERIMENT_PROPOSED.value,
                    EventType.HYPOTHESIS_PROPOSED.value,
                    EventType.HYPOTHESIS_REJECTED.value,
                    EventType.HYPOTHESIS_SUSPENDED.value,
                ],
                projection={
                    "evidence": [
                        {
                            "id": e.id,
                            "experiment_id": e.experiment_id,
                            "observation": _short(e.observation),
                            "passed": e.attributes.get("passed"),
                        }
                        for e in pending
                    ],
                    "hypotheses": _hyp_summary(state),
                    "metrics": _metrics_summary(state),
                },
            )

    if state.evidence and len(state.interpretations) == 1:
        only = next(iter(state.interpretations.values()))
        if only.outcome.value != "SUPPORTS":
            return Task(
                case_id=state.case_id,
                role=AgentRole.ADVERSARY,
                objective="Submit a competing interpretation of the latest evidence, or concede sufficiency.",
                allowed_event_types=[
                    EventType.INTERPRETATION_SUBMITTED.value,
                    EventType.EXPERIMENT_PROPOSED.value,
                ],
                projection=_slice_for_role(state, AgentRole.ADVERSARY),
                hints=[
                    ANNOUNCE_HANDOFF_HINT,
                    "Announce this Adversary handoff in chat before challenging.",
                ],
            )

    unrebutted = unrebutted_supports_evidence_ids(state)
    if unrebutted:
        return _adversary_rebuttal_task(state, unrebutted)

    supported = [
        h
        for h in state.hypotheses.values()
        if h.status
        in {
            HypothesisStatus.SUPPORTED,
            HypothesisStatus.STRONGLY_SUPPORTED,
            HypothesisStatus.PLAUSIBLE,
        }
        and any(
            i.hypothesis_id == h.id and i.outcome.value == "SUPPORTS"
            for i in state.interpretations.values()
        )
    ]
    if supported and state.evidence:
        best = supported[0]
        successful_fix = any(
            (e.experiment_class == "intervention" or bool(e.patch))
            and e.status == ExperimentStatus.COMPLETED
            and any(
                ev.experiment_id == e.id and ev.attributes.get("passed") is True
                for ev in state.evidence.values()
            )
            for e in state.experiments.values()
        )
        pending_intervention = any(
            (e.experiment_class == "intervention" or bool(e.patch))
            and e.status
            in {
                ExperimentStatus.PROPOSED,
                ExperimentStatus.APPROVED,
                ExperimentStatus.SCHEDULED,
                ExperimentStatus.RUNNING,
            }
            for e in state.experiments.values()
        )
        # Report-only path: observational evidence is enough to accept when no
        # intervention was proposed (investigate skill). Incident skill proposes
        # interventions explicitly before this branch is reached for approve/run.
        if successful_fix or not pending_intervention:
            return Task(
                case_id=state.case_id,
                role=AgentRole.JUDGE,
                objective=(
                    "Fix verified. Accept root cause or escalate if residual risk remains."
                    if successful_fix
                    else (
                        "Observational evidence supports a root-cause hypothesis. "
                        "Accept root cause (report-only) or escalate if residual risk remains. "
                        "Do not require an intervention unless one was proposed."
                    )
                ),
                allowed_event_types=[
                    EventType.ROOT_CAUSE_ACCEPTED.value,
                    EventType.UNKNOWN_RESOLVED.value,
                    EventType.INVESTIGATION_ESCALATED.value,
                    EventType.HYPOTHESIS_REJECTED.value,
                    EventType.HYPOTHESIS_SUSPENDED.value,
                    EventType.HYPOTHESIS_PROMOTED.value,
                    EventType.EXPERIMENT_PROPOSED.value,
                ],
                projection={
                    "candidate_hypothesis_id": best.id,
                    "hypotheses": _hyp_summary(state),
                    "interpretations": _interp_summary(state),
                    "metrics": _metrics_summary(state),
                    "successful_fix": successful_fix,
                    "report_only": not successful_fix,
                },
                hints=[
                    ANNOUNCE_HANDOFF_HINT,
                    "Investigate skill: accept and write issues/<slug>.md; fix via incident skill.",
                    "Incident skill: may still propose experiment_class=intervention before accept.",
                ],
            )
        return Task(
            case_id=state.case_id,
            role=AgentRole.ANALYST,
            objective=(
                "Evidence supports a root-cause hypothesis. A pending intervention exists — "
                "refine or wait for approve/verify, or escalate if blocked."
            ),
            allowed_event_types=[
                EventType.EXPERIMENT_PROPOSED.value,
                EventType.INVESTIGATION_ESCALATED.value,
            ],
            projection={
                "candidate_hypothesis_id": best.id,
                "hypotheses": _hyp_summary(state),
                "interpretations": _interp_summary(state),
                "metrics": _metrics_summary(state),
            },
            hints=[
                ANNOUNCE_HANDOFF_HINT,
                "Prefer completing the pending intervention verification before accept.",
                "Escalate only for groundbreaking, safety, or human-only blockers.",
            ],
        )

    # Starvation recovery — still counting toward stall escalation
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
        hints=[
            ANNOUNCE_HANDOFF_HINT,
            "Starvation policy: waiting indefinitely is prohibited.",
            "Escalate only for groundbreaking, safety, or human-only blockers.",
        ],
    )


def projection_size_bytes(task: Task) -> int:
    return len(json.dumps(task.projection, default=str).encode("utf-8"))

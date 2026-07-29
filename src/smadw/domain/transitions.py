from __future__ import annotations

from smadw.domain.models import ExperimentStatus, HypothesisStatus, UnknownStatus

UNKNOWN_TRANSITIONS: dict[UnknownStatus, set[UnknownStatus]] = {
    UnknownStatus.DISCOVERED: {UnknownStatus.ACTIVE, UnknownStatus.ABANDONED},
    UnknownStatus.ACTIVE: {
        UnknownStatus.PARTIALLY_RESOLVED,
        UnknownStatus.RESOLVED,
        UnknownStatus.ABANDONED,
    },
    UnknownStatus.PARTIALLY_RESOLVED: {
        UnknownStatus.RESOLVED,
        UnknownStatus.ACTIVE,
        UnknownStatus.ABANDONED,
    },
    UnknownStatus.RESOLVED: {UnknownStatus.ACTIVE},  # reopen path via UnknownReopened
    UnknownStatus.ABANDONED: set(),
}

HYPOTHESIS_POSITIVE: dict[HypothesisStatus, set[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: {HypothesisStatus.PLAUSIBLE},
    HypothesisStatus.PLAUSIBLE: {HypothesisStatus.SUPPORTED},
    HypothesisStatus.SUPPORTED: {HypothesisStatus.STRONGLY_SUPPORTED},
    HypothesisStatus.STRONGLY_SUPPORTED: {HypothesisStatus.ACCEPTED},
    HypothesisStatus.ACCEPTED: set(),
}

HYPOTHESIS_NEGATIVE: dict[HypothesisStatus, set[HypothesisStatus]] = {
    HypothesisStatus.PROPOSED: {HypothesisStatus.WEAKENED, HypothesisStatus.REJECTED},
    HypothesisStatus.PLAUSIBLE: {HypothesisStatus.WEAKENED, HypothesisStatus.SUSPENDED, HypothesisStatus.REJECTED},
    HypothesisStatus.SUPPORTED: {HypothesisStatus.WEAKENED, HypothesisStatus.SUSPENDED, HypothesisStatus.REJECTED},
    HypothesisStatus.STRONGLY_SUPPORTED: {
        HypothesisStatus.WEAKENED,
        HypothesisStatus.SUSPENDED,
        HypothesisStatus.REJECTED,
    },
    HypothesisStatus.WEAKENED: {HypothesisStatus.SUSPENDED, HypothesisStatus.REJECTED, HypothesisStatus.PLAUSIBLE},
    HypothesisStatus.SUSPENDED: {HypothesisStatus.REJECTED, HypothesisStatus.PLAUSIBLE},
    HypothesisStatus.REJECTED: set(),
    HypothesisStatus.ACCEPTED: set(),
}

EXPERIMENT_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
    ExperimentStatus.PROPOSED: {
        ExperimentStatus.APPROVED,
        ExperimentStatus.CANCELLED,
        ExperimentStatus.EXPIRED,
    },
    ExperimentStatus.APPROVED: {
        ExperimentStatus.SCHEDULED,
        ExperimentStatus.CANCELLED,
        ExperimentStatus.EXPIRED,
    },
    ExperimentStatus.SCHEDULED: {
        ExperimentStatus.RUNNING,
        ExperimentStatus.CANCELLED,
        ExperimentStatus.EXPIRED,
    },
    ExperimentStatus.RUNNING: {
        ExperimentStatus.COMPLETED,
        ExperimentStatus.FAILED,
        ExperimentStatus.CANCELLED,
    },
    ExperimentStatus.COMPLETED: set(),
    ExperimentStatus.FAILED: set(),
    ExperimentStatus.CANCELLED: set(),
    ExperimentStatus.EXPIRED: set(),
}


def can_transition_unknown(current: UnknownStatus, target: UnknownStatus) -> bool:
    return target in UNKNOWN_TRANSITIONS.get(current, set())


def can_promote_hypothesis(current: HypothesisStatus, target: HypothesisStatus) -> bool:
    return target in HYPOTHESIS_POSITIVE.get(current, set()) or target in HYPOTHESIS_NEGATIVE.get(
        current, set()
    )


def can_transition_experiment(current: ExperimentStatus, target: ExperimentStatus) -> bool:
    return target in EXPERIMENT_TRANSITIONS.get(current, set())

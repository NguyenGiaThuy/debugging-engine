from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0.0"


def new_id() -> str:
    return str(uuid4())


class AgentRole(StrEnum):
    ANALYST = "Analyst"
    ADVERSARY = "Adversary"
    IMPLEMENTER = "Implementer"
    VERIFIER = "Verifier"
    JUDGE = "Judge"
    HUMAN = "Human"
    SYSTEM = "System"


class ObjectionCategory(StrEnum):
    MISSING_EVIDENCE = "Missing Evidence"
    ALTERNATIVE_HYPOTHESIS = "Alternative Hypothesis"
    INVALID_ASSUMPTION = "Invalid Assumption"
    INCOMPLETE_EXPLANATION = "Incomplete Explanation"
    UNSUPPORTED_CAUSAL_LINK = "Unsupported Causal Link"
    EXPERIMENT_DESIGN_FLAW = "Experiment Design Flaw"


class UnknownStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    ACTIVE = "ACTIVE"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    PLAUSIBLE = "PLAUSIBLE"
    SUPPORTED = "SUPPORTED"
    STRONGLY_SUPPORTED = "STRONGLY_SUPPORTED"
    ACCEPTED = "ACCEPTED"
    WEAKENED = "WEAKENED"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


class ExperimentStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class InformationGain(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MINIMAL = "MINIMAL"


class ExperimentCost(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InterpretationOutcome(StrEnum):
    SUPPORTS = "SUPPORTS"
    WEAKENS = "WEAKENS"
    INCONCLUSIVE = "INCONCLUSIVE"


class InvestigationStatus(StrEnum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class EventType(StrEnum):
    CASE_CREATED = "CaseCreated"
    INVESTIGATION_ACTIVATED = "InvestigationActivated"
    INVESTIGATION_RESOLVED = "InvestigationResolved"
    INVESTIGATION_ESCALATED = "InvestigationEscalated"
    INVESTIGATION_ABANDONED = "InvestigationAbandoned"
    UNKNOWN_DISCOVERED = "UnknownDiscovered"
    UNKNOWN_RESOLVED = "UnknownResolved"
    UNKNOWN_REOPENED = "UnknownReopened"
    HYPOTHESIS_PROPOSED = "HypothesisProposed"
    HYPOTHESIS_PROMOTED = "HypothesisPromoted"
    HYPOTHESIS_WEAKENED = "HypothesisWeakened"
    HYPOTHESIS_SUSPENDED = "HypothesisSuspended"
    HYPOTHESIS_REJECTED = "HypothesisRejected"
    EXPERIMENT_PROPOSED = "ExperimentProposed"
    EXPERIMENT_APPROVED = "ExperimentApproved"
    EXPERIMENT_SCHEDULED = "ExperimentScheduled"
    EXPERIMENT_STARTED = "ExperimentStarted"
    EXPERIMENT_COMPLETED = "ExperimentCompleted"
    EXPERIMENT_CANCELLED = "ExperimentCancelled"
    EXPERIMENT_EXPIRED = "ExperimentExpired"
    EVIDENCE_RECORDED = "EvidenceRecorded"
    INTERPRETATION_SUBMITTED = "InterpretationSubmitted"
    INTERPRETATION_WITHDRAWN = "InterpretationWithdrawn"
    ROOT_CAUSE_ACCEPTED = "RootCauseAccepted"
    INVESTIGATION_CLOSED = "InvestigationClosed"
    VALIDATION_FAILED = "ValidationFailed"
    VERIFICATION_FAILED = "VerificationFailed"
    IMPLEMENTATION_FAILED = "ImplementationFailed"
    PATCH_APPLIED = "PatchApplied"
    UNKNOWN_PARTIALLY_RESOLVED = "UnknownPartiallyResolved"
    HUMAN_RESPONSE_RECEIVED = "HumanResponseReceived"
    KNOWLEDGE_VALIDATED = "KnowledgeValidated"


class DomainEvent(BaseModel):
    event_id: str = Field(default_factory=new_id)
    case_id: str
    event_type: EventType
    timestamp: str
    producer: str
    schema_version: str = SCHEMA_VERSION
    correlation_id: str = Field(default_factory=new_id)
    causation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Unknown(BaseModel):
    id: str
    title: str
    description: str = ""
    priority: str = "HIGH"
    status: UnknownStatus = UnknownStatus.DISCOVERED
    related_components: list[str] = Field(default_factory=list)
    parent_unknown: str | None = None
    child_unknowns: list[str] = Field(default_factory=list)
    revision: int = 1


class Hypothesis(BaseModel):
    id: str
    unknown_id: str
    title: str
    explanation: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    assumptions: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    revision: int = 1
    objection_category: str | None = None


class VerificationSpec(BaseModel):
    command: list[str] = Field(
        default_factory=lambda: ["python", "-m", "pytest", "-q"]
    )
    expected_exit_code: int = 0
    working_directory: str = "."
    description: str = ""
    # Optional rich contract (Spec Part V): metric names, numeric thresholds, baselines.
    metrics: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    baselines: dict[str, float] = Field(default_factory=dict)


class Experiment(BaseModel):
    id: str
    unknown_id: str
    title: str
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    information_gain: InformationGain = InformationGain.MEDIUM
    cost: ExperimentCost = ExperimentCost.LOW
    affected_hypotheses: list[str] = Field(default_factory=list)
    expected_observations: list[str] = Field(default_factory=list)
    verification_spec: VerificationSpec | None = None
    experiment_class: str = "observational"  # observational | intervention
    patch: dict[str, str] | None = None  # path -> new content for intervention stubs
    revision: int = 1


class Evidence(BaseModel):
    id: str
    experiment_id: str
    observation: str
    category: str = "Test Result"
    provenance: str = "verifier"
    reproducibility: str = "repeatable"
    collection_method: str = "pytest"
    reliability: str = "HIGH"
    attributes: dict[str, Any] = Field(default_factory=dict)
    revision: int = 1


class Interpretation(BaseModel):
    id: str
    evidence_id: str
    hypothesis_id: str
    outcome: InterpretationOutcome
    rationale: str
    producer: str
    objection_category: str | None = None
    revision: int = 1


class CaseState(BaseModel):
    case_id: str
    title: str = ""
    status: InvestigationStatus = InvestigationStatus.CREATED
    issue_path: str | None = None
    unknowns: dict[str, Unknown] = Field(default_factory=dict)
    hypotheses: dict[str, Hypothesis] = Field(default_factory=dict)
    experiments: dict[str, Experiment] = Field(default_factory=dict)
    evidence: dict[str, Evidence] = Field(default_factory=dict)
    interpretations: dict[str, Interpretation] = Field(default_factory=dict)
    decision_state: dict[str, Any] = Field(default_factory=dict)
    revision: int = 0
    event_count: int = 0

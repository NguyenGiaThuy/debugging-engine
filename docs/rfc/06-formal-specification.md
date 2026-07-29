# SMADW v3.1

# Part VI — Formal Specification

> **Status:** Normative
>
> This chapter defines the canonical schemas, contracts, protocols, state machines, validation rules, and extension interfaces of SMADW. Any implementation claiming SMADW compliance MUST satisfy the requirements in this chapter.

---

# 1. Scope

Part VI defines:

* Canonical object schemas
* Event envelope
* Domain events
* Agent contracts
* State transition rules
* Validation rules
* Query interfaces
* Extension points
* Error model

Implementation technologies are intentionally unspecified.

---

# 2. Schema Versioning

Every serialized object MUST contain:

```json
{
  "schema_version": "3.1.0"
}
```

Backward-compatible additions MUST increment the minor version.

Breaking changes MUST increment the major version.

Consumers MUST reject unsupported major versions.

---

# 3. Canonical Event Envelope

All domain events MUST use the same envelope.

```json
{
  "event_id": "uuid",
  "case_id": "uuid",
  "event_type": "HypothesisProposed",
  "timestamp": "2026-07-29T12:34:56Z",
  "producer": "Analyst",
  "schema_version": "3.1.0",
  "correlation_id": "uuid",
  "causation_id": "uuid",
  "payload": { }
}
```

---

## Field Definitions

| Field          | Description                                    |
| -------------- | ---------------------------------------------- |
| event_id       | Globally unique identifier                     |
| case_id        | Investigation identifier                       |
| event_type     | Canonical event type                           |
| producer       | Producing architectural component              |
| correlation_id | Links events belonging to the same workflow    |
| causation_id   | References the event that triggered this event |
| payload        | Event-specific data                            |

---

# 4. Canonical Investigation Objects

The following objects are normative.

```text
Case

Unknown

Hypothesis

Experiment

Evidence

Interpretation
```

Every implementation MUST support all six.

No implementation may redefine their meaning.

---

# 5. State Machines

Every object has an explicit lifecycle.

Example

Unknown

```text
DISCOVERED

↓

ACTIVE

↓

PARTIALLY_RESOLVED

↓

RESOLVED
```

Experiment

```text
PROPOSED

↓

APPROVED

↓

SCHEDULED

↓

RUNNING

↓

COMPLETED
```

Hypothesis

```text
PROPOSED

↓

PLAUSIBLE

↓

SUPPORTED

↓

STRONGLY_SUPPORTED

↓

ACCEPTED
```

Negative transitions

```text
WEAKENED

↓

SUSPENDED

↓

REJECTED
```

Transitions not defined by this specification are invalid.

---

# 6. Validation Rules

Every event MUST pass validation before mutating Case State.

Examples

HypothesisProposed

Requires

* target Unknown exists
* title not empty
* explanation provided

ExperimentApproved

Requires

* experiment exists
* dependency validation succeeds
* approval authority present

EvidenceRecorded

Requires

* experiment completed
* provenance defined
* timestamp present

Validation failure produces a new event.

It never silently modifies state.

---

# 7. Domain Events

SMADW defines a fixed vocabulary of domain events.

### Investigation

```text
CaseCreated
InvestigationActivated
InvestigationResolved
InvestigationEscalated
InvestigationAbandoned
```

---

### Unknown

```text
UnknownDiscovered
UnknownResolved
UnknownReopened
```

---

### Hypothesis

```text
HypothesisProposed
HypothesisPromoted
HypothesisWeakened
HypothesisSuspended
HypothesisRejected
```

---

### Experiment

```text
ExperimentApproved
ExperimentScheduled
ExperimentStarted
ExperimentCompleted
ExperimentCancelled
ExperimentExpired
```

---

### Evidence

```text
EvidenceRecorded
InterpretationSubmitted
InterpretationWithdrawn
```

---

### Decisions

```text
RootCauseAccepted
InvestigationClosed
```

No implementation may invent new core event types without extending the specification.

---

# 8. Agent Contract

Every architectural agent implements the same logical interface.

```typescript
interface Agent {

    read(Query)

    execute(Task)

    emit(DomainEvent[])
}
```

Agents never write Case State directly.

Only events modify investigation state.

---

# 9. Query Interface

Agents retrieve projections.

Never entire Case State.

Example

```text
Query

↓

Projection

↓

Agent
```

Typical queries

```text
Unknown #17

Open Experiments

Evidence for Hypothesis X

Unresolved Interpretations

Pending Dependencies
```

---

# 10. Case State Projection

Case State is materialized from Event Log.

```text
Event Log

↓

Projection Engine

↓

Case State
```

Projection implementations MAY vary.

Observable behavior MUST NOT.

---

# 11. Event Bus Contract

The Event Bus MUST provide

* durable delivery
* ordering per Case
* replay
* subscriptions
* acknowledgements

The Event Bus MUST NOT

* interpret payloads
* mutate Case State
* perform scheduling

---

# 12. Error Model

Errors are represented as domain events.

Example

```text
ValidationFailed

VerificationFailed

ImplementationFailed

KnowledgeRetrievalFailed

HumanTimeout
```

Errors are first-class investigation artifacts.

Not exceptions.

---

# 13. Extension Points

SMADW intentionally separates architecture from implementation.

The following interfaces are replaceable.

---

## Language Model Provider

Examples

* OpenAI
* Anthropic
* Ollama
* Local models

Architecture remains identical.

---

## Knowledge Store

Examples

* PostgreSQL
* Neo4j
* Qdrant
* Elasticsearch

---

## Event Bus

Examples

* Kafka
* RabbitMQ
* Azure Service Bus
* NATS
* Redis Streams

---

## Verification Platform

Examples

* GitHub Actions
* Jenkins
* Azure Pipelines
* Local execution

---

## Observability

Examples

* OpenTelemetry
* Grafana
* New Relic
* Datadog

---

# 14. Compliance Levels

To encourage adoption, SMADW defines three compliance tiers.

### Level 1 — Core Compliance

Requirements:

* Canonical investigation objects
* Event Log
* Case State projection
* Agent contracts
* Domain events

Suitable for research prototypes and educational implementations.

---

### Level 2 — Operational Compliance

Adds:

* Event Bus
* Dependency graph
* Parallel execution
* Verification specifications
* Human escalation

Suitable for production deployments.

---

### Level 3 — Full Compliance

Adds:

* Knowledge validation
* Fingerprint retrieval
* Governance
* Schema versioning
* Extension interfaces
* Complete auditability

Represents full SMADW v3.1 conformance.

---

# 15. Security Considerations

Implementations SHOULD support:

* authentication
* authorization
* immutable audit logs
* encrypted event transport
* access-controlled knowledge repositories
* sensitive data redaction
* investigation isolation between tenants

Security policies are implementation-specific but MUST preserve the architectural invariants.

---

# 16. Interoperability

Two implementations are interoperable if they:

* understand canonical events,
* honor state transition rules,
* implement required object schemas,
* preserve event ordering,
* expose equivalent query semantics.

Implementation language is irrelevant.

---

# 17. Reference Implementation Requirements

A conforming reference implementation MUST demonstrate:

* Event sourcing with Case State projection.
* Event-driven orchestration.
* The seven architectural agents.
* Immutable evidence.
* Query-based Case State access.
* Parallel experiment scheduling with dependency enforcement.
* Verification Specifications.
* Knowledge validation before persistence.
* Replay of historical investigations from the Event Log.

These capabilities serve as executable proof that the specification is complete and internally consistent.

---

# Judge Review — Part VI

**Status:** ✅ Approved with one strategic recommendation.

The formal specification successfully separates architecture from implementation and provides a stable interoperability contract. However, the specification would benefit from one final chapter that is not normative but highly practical: a **Reference Architecture and Implementation Guide**. This chapter should illustrate how the abstract concepts map onto a concrete system—repositories, services, databases, event buses, APIs, deployment topology, and an end-to-end investigation example. By keeping that material informative rather than normative, SMADW remains technology-agnostic while giving implementers a clear path from specification to working software. That becomes the role of Part VII, completing the transition from architectural standard to implementable ecosystem.

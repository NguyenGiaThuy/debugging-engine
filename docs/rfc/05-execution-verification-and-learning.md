# SMADW v3.1

# Part V — Execution, Verification & Learning

> **Status:** Normative
>
> This chapter defines how approved experiments are executed, how evidence is produced, how investigations communicate through events, and how validated investigations become reusable organizational knowledge.

---

# 1. Purpose

An investigation has value only if it produces reproducible evidence.

Reasoning proposes experiments.

Execution performs them.

Verification records observations.

Learning preserves validated knowledge.

This chapter defines that execution pipeline.

---

# 2. Execution Architecture

Execution is intentionally separated from orchestration.

```text
Analyst
    │
Experiment Proposal
    │
Judge Approval
    │
    ▼
Execution Pipeline
    │
Verifier
    │
Evidence
    │
Event Bus
    │
Investigation Orchestrator
```

Notice that neither the Analyst nor the Judge executes experiments.

---

# 3. Event Bus

The Event Bus is infrastructure.

It is **not** an architectural agent.

Its sole responsibility is reliable delivery of domain events.

Examples

```
ExperimentStarted

ExperimentCompleted

EvidenceRecorded

VerificationFailed

HumanResponseReceived

KnowledgeValidated
```

Every execution component publishes events.

The Investigation Orchestrator subscribes to those events.

---

## Requirements

The Event Bus MUST

* preserve event ordering within an investigation
* guarantee at-least-once delivery
* support asynchronous execution
* allow replay from durable storage

It MUST NOT

* interpret events
* modify Case State
* perform scheduling

---

# 4. Execution Pipeline

Every approved experiment follows the same lifecycle.

```text
ExperimentApproved

↓

Implementation

↓

Execution

↓

Verification

↓

Evidence

↓

EvidenceRecorded Event
```

Every stage either succeeds or emits a failure event.

No silent failures exist.

---

# 5. Experiment Classes

SMADW recognizes two execution pipelines.

---

## Observational Experiments

Observe the system without modifying behavior.

Examples

* Enable tracing
* Collect metrics
* Download logs
* Capture thread dumps
* Observe production traffic

Pipeline

```text
Configure Observation

↓

Collect Data

↓

Normalize

↓

Evidence
```

---

## Intervention Experiments

Modify system behavior.

Examples

* Apply patch
* Disable cache
* Increase timeout
* Inject fault
* Deploy branch

Pipeline

```text
Implement

↓

Build

↓

Deploy

↓

Execute

↓

Verify

↓

Evidence
```

Intervention experiments carry higher operational risk and SHOULD require stricter approval policies.

---

# 6. Verification Specification

The Verifier executes only against an explicit Verification Specification.

A specification defines

* metrics
* expected observations
* acceptance thresholds
* comparison baseline
* required artifacts

Example

```yaml
metrics:
  - latency
  - throughput
  - error_rate

baseline:
  production

expected:
  latency:
    direction: decrease

thresholds:
  latency:
    max: 20ms

artifacts:
  - logs
  - traces
```

The Verifier MUST NOT infer missing requirements.

---

# 7. Evidence Production

Verification produces immutable Evidence objects.

Evidence records

* observation
* timestamp
* provenance
* reproducibility
* collection method
* associated experiment

Evidence never contains explanations.

---

# 8. Evidence Quality

Not all evidence has equal strength.

Instead of numerical confidence, SMADW evaluates evidence along qualitative dimensions.

| Attribute       | Description                                        |
| --------------- | -------------------------------------------------- |
| Reliability     | Was the evidence collected correctly?              |
| Relevance       | Does it directly address the Unknown?              |
| Reproducibility | Can the observation be repeated?                   |
| Completeness    | Does it sufficiently characterize the observation? |
| Independence    | Is it corroborated by unrelated sources?           |

These attributes guide interpretation.

They never become probabilities.

---

# 9. Verification Failure

Verification failures are informative.

Examples

* build failed
* deployment failed
* benchmark invalid
* required logs missing
* timeout exceeded

Each failure produces structured events.

Example

```
VerificationFailed

reason:
MissingRequiredMetric
```

The investigation may continue despite verification failures.

---

# 10. Learning Pipeline

Not every completed investigation becomes organizational knowledge.

Knowledge must be validated.

Pipeline

```text
Completed Investigation

↓

Candidate Knowledge

↓

Adversary Review

↓

Knowledge Validation

↓

Knowledge Repository
```

This prevents accidental learning from incorrect conclusions.

---

# 11. Knowledge Validation

Knowledge is accepted only if

* investigation completed successfully
* verification succeeded
* root cause accepted
* no unresolved objections remain
* evidence is reproducible
* organizational policy permits publication

Knowledge is therefore curated rather than accumulated.

---

# 12. Case Fingerprints

Knowledge retrieval does not rely solely on semantic similarity.

Every completed investigation generates a fingerprint.

Fingerprint dimensions include

```
Affected Components

Technology Stack

Error Signatures

Failure Mode

Observed Symptoms

Performance Metrics

Environment

Root Cause Category

Verification Pattern
```

Fingerprints support efficient retrieval across large knowledge repositories.

---

# 13. Knowledge Retrieval

When a new investigation begins, the Knowledge Service MAY retrieve similar validated investigations.

Retrieval SHOULD prioritize

1. Matching failure signatures.
2. Similar architectural components.
3. Similar verification patterns.
4. Similar environmental conditions.

Retrieved knowledge is advisory.

It never automatically creates hypotheses.

---

# 14. Knowledge Aging

Knowledge can become obsolete.

The repository SHOULD support

* versioning
* deprecation
* supersession
* expiration

Deprecated knowledge remains historically available but SHOULD NOT influence new investigations unless explicitly requested.

---

# 15. Organizational Memory

SMADW distinguishes between three classes of knowledge.

| Type                  | Purpose                                                    |
| --------------------- | ---------------------------------------------------------- |
| Investigation Records | Complete event history of a specific case                  |
| Validated Knowledge   | Reusable engineering knowledge derived from investigations |
| Reference Patterns    | Organizational best practices and architectural guidance   |

This separation prevents historical investigations from being mistaken for universally applicable rules.

---

# 16. Learning Governance

Organizations SHOULD establish governance policies covering

* publication approval
* confidential information removal
* compliance review
* retention periods
* access control

The architecture intentionally separates technical validation from organizational governance.

---

# 17. Architectural Properties

The execution and learning architecture provides:

* **Asynchronous execution** through the Event Bus.
* **Deterministic evidence production** via Verification Specifications.
* **Immutable observations** separated from interpretations.
* **Curated organizational learning** through explicit validation.
* **Scalable knowledge retrieval** using investigation fingerprints.
* **Long-term maintainability** through knowledge versioning and aging.

Execution therefore becomes an auditable, reproducible process rather than an ad hoc collection of scripts and prompts.

---

# Judge Review — Part V

**Status:** ✅ Approved with two recommendations for Part VI.

1. **Define the Event Envelope.** The Event Bus currently transports domain events, but Part VI should specify a canonical event envelope (e.g., `event_id`, `case_id`, `event_type`, `timestamp`, `producer`, `schema_version`, `payload`, `correlation_id`, `causation_id`). This ensures interoperability between implementations.

2. **Formalize Extension Points.** While SMADW intentionally defines seven architectural agents, implementations will inevitably integrate different LLMs, verification tools, CI/CD systems, tracing platforms, and knowledge stores. Part VI should explicitly define extension interfaces so that implementations can substitute infrastructure without altering the architectural contracts. This keeps SMADW implementation-agnostic while preserving interoperability.

These additions will allow Part VI to function as a true implementation specification rather than merely a conceptual reference.

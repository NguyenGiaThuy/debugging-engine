# Debugging Engine v3.1

# Part III — Investigation Model

> **Status:** Normative
>
> This chapter defines the canonical investigation state. Every investigation object, lifecycle, relationship, and event is specified here. No later chapter may introduce new first-class investigation objects without updating this chapter.

---

# 1. Overview

Every Debugging Engine investigation is represented as a **Case State**.

The Case State is the authoritative representation of everything the system knows about an investigation at a given point in time.

It is not a conversation history.

It is not a prompt.

It is not agent memory.

It is a structured, versioned, event-derived state machine.

Every agent reads from it.

Every agent writes to it indirectly through domain events.

---

# 2. Case State

The Case State is the single source of truth for *current* investigation state.

It contains only current state.

Historical changes are preserved separately through the Event Log.

```
Case State
│
├── Metadata
├── Unknown Registry
├── Hypothesis Graph
├── Experiment Registry
├── Evidence Registry
├── Interpretation Registry
├── Decision State (materialized from Decision Events)
├── Investigation Timeline
└── Revision Version
```

The Case State MUST be reconstructible by replaying the Event Log.

Therefore

**Event Log = Source of Truth**

Case State = Materialized View

This distinction is extremely important.

Unlike v3.0, the Case State is **not** the primary persistence model.

It is a projection.

Architectural decisions (for example accepting a root cause or escalating an investigation) are recorded as **Decision Events** in the Event Log. Current decision status is materialized into Case State Decision State. Decisions are not first-class investigative objects.

---

# 3. Event Log

Every mutation is recorded as an immutable event.

Examples

```
CaseCreated

UnknownDiscovered

HypothesisProposed

ExperimentApproved

ExperimentStarted

ExperimentCompleted

EvidenceRecorded

InterpretationSubmitted

InterpretationResolved

RootCauseAccepted

InvestigationEscalated
```

Events are immutable.

Nothing edits history.

---

# 4. Investigation Objects

Debugging Engine defines exactly five canonical first-class investigation objects, plus the Case that contains them.

```
Unknown

↓

Hypothesis

↓

Experiment

↓

Evidence

↓

Interpretation
```

Architectural conclusions are represented as **Decision Events** (for example `RootCauseAccepted`, `InvestigationEscalated`, `InvestigationClosed`) recorded in the Event Log, with current decision status materialized in Case State.

Everything else is supporting infrastructure.

---

# 5. Unknown

## Definition

An Unknown represents a question whose answer is currently insufficiently supported.

Unknowns define investigation scope.

Examples

```
Why is request latency increasing?

Why does the service restart?

Why does memory usage never decrease?
```

Unknowns are never assumptions.

Unknowns are not hypotheses.

They are questions.

---

### Unknown Lifecycle

```
DISCOVERED

↓

ACTIVE

↓

PARTIALLY_RESOLVED

↓

RESOLVED
```

or

```
ACTIVE

↓

ABANDONED
```

---

### Unknown Schema

```
Unknown

id

title

description

priority

status

created_at

resolved_at

related_components

parent_unknown

child_unknowns
```

---

# 6. Hypothesis

A Hypothesis proposes a technical explanation for one Unknown.

Every Hypothesis MUST reference exactly one target Unknown.

Multiple hypotheses may explain the same Unknown.

---

Example

Unknown

```
Why is latency increasing?
```

Hypothesis A

```
Redis lock contention
```

Hypothesis B

```
Database connection pool exhaustion
```

Hypothesis C

```
GC pauses
```

All coexist.

Debugging Engine never assumes exclusivity.

---

## Hypothesis Lifecycle

```
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

Negative evidence

```
WEAKENED

↓

SUSPENDED

↓

REJECTED
```

Notice

No numerical confidence exists.

---

### Promotion Rules

A hypothesis advances only through evidence.

Reasoning alone never promotes a hypothesis.

Example

```
PROPOSED

+

Supporting Evidence

↓

PLAUSIBLE
```

Repeated unsupported reasoning changes nothing.

---

# 7. Experiment

Experiments exist to reduce uncertainty.

Not to prove hypotheses.

Each experiment MUST declare

* target Unknown
* expected observations
* competing hypotheses affected
* estimated information gain
* estimated execution cost

Estimated information gain is a qualitative planning heuristic. Its levels and use in scheduling are defined in Part IV. It is not a probability and not numerical confidence.

---

## Experiment Types

Debugging Engine recognizes two categories.

### Observational

No system modification.

Examples

```
Enable logging

Collect traces

Capture metrics

Observe production traffic
```

---

### Intervention

Changes system behavior.

Examples

```
Modify implementation

Disable cache

Inject fault

Change configuration

Increase timeout
```

These require implementation.

---

## Experiment Lifecycle

```
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

Alternative

```
FAILED

CANCELLED

EXPIRED
```

---

# 8. Evidence

Evidence is an immutable observation produced by experiment execution.

Evidence never explains.

Evidence only reports.

Example

```
Average latency

142 ms
```

Not

```
Redis caused latency.
```

That is interpretation.

---

### Evidence Categories

```
Benchmark

Log

Trace

Test Result

Metric

Profile

Stack Trace

Human Observation
```

Categories describe provenance.

Not importance.

---

### Evidence Attributes

Every Evidence object records

* source reliability
* collection method
* timestamp
* reproducibility
* related experiment

Importance is not stored.

Importance belongs to interpretation.

---

# 9. Interpretation

Interpretations connect evidence to hypotheses.

Multiple interpretations may exist simultaneously.

Example

Evidence

```
Redis latency increased.
```

Analyst

```
Supports Redis lock contention.
```

Adversary

```
Database retries indirectly caused Redis saturation.
```

Both are stored.

Nothing is discarded.

---

## Interpretation Outcome

Interpretations classify evidence as

```
SUPPORTS

WEAKENS

INCONCLUSIVE
```

INCONCLUSIVE does not affect hypothesis state.

Instead it motivates further experiments.

---

# 10. Decision Events

Architectural conclusions are **Decision Events**, not first-class investigation objects.

Examples

```
ExperimentApproved

HypothesisSuspended

RootCauseAccepted

InvestigationEscalated

InvestigationClosed
```

Every decision event MUST reference

* supporting evidence
* competing interpretations considered
* decision rationale
* responsible authority

Decision events are immutable.

If a conclusion changes, a new Decision Event is appended and Case State Decision State is updated. History is never rewritten.

---

# 11. Hypothesis Graph

Hypotheses form a directed acyclic graph.

Edges represent explanatory refinement.

Example

```
High Latency

↓

Redis Bottleneck

↓

Lock Contention
```

The graph represents reasoning.

Not scheduling.

---

# 12. Experiment Dependency Graph

This is a new first-class concept in v3.1.

Unlike the Hypothesis Graph,

this graph models execution.

Edges represent

* shared resources
* ordering constraints
* interference risks
* mutual exclusion

Example

```
Experiment A

↓

Requires Database Snapshot

↓

Experiment B
```

or

```
Experiment A

×

Experiment B

Conflict

Verbose logging
```

The Judge schedules using this graph.

Not the Hypothesis Graph.

---

# 13. Interpretation Resolution

Interpretations are not automatically merged.

Instead they enter arbitration.

```
Evidence

↓

Interpretations

↓

Judge

↓

Is existing evidence sufficient to resolve the disagreement?
```

If

Yes

↓

Investigation proceeds (Decision Events may be emitted as warranted)

If

No

↓

Design new discriminating experiment

This is a critical innovation.

Disagreement produces experiments,

not debate.

The Judge MUST NOT decide which interpretation is technically correct. Technical correctness remains with evidence. The Judge determines only whether current evidence is sufficient to proceed or whether additional experimentation is required.

---

# 14. Root Cause Acceptance

A root cause may be accepted only if all conditions hold.

1.

Every relevant Unknown is resolved.

2.

Every required verification succeeds.

3.

No unresolved critical objection remains.

4.

Competing hypotheses are

* rejected

or

* suspended

or

lack supporting evidence.

5.

Evidence sufficiently explains observed behavior.

Acceptance is therefore rule-driven.

Not subjective.

Acceptance is recorded by emitting a `RootCauseAccepted` Decision Event.

---

# 15. Case Query API

Agents never receive the complete Case State.

Instead they request views.

Example

```
Analyst

↓

Unknown

#42

↓

Relevant hypotheses

↓

Relevant evidence

↓

Previous interpretations
```

The Case State exposes projections,

not snapshots.

This solves scalability.

---

# 16. Revision Model

Every investigation object is versioned.

Objects are immutable.

Updates create new revisions.

```
Hypothesis

v1

↓

v2

↓

v3
```

References always point to the latest accepted revision unless historical inspection is requested.

---

# 17. Architectural Consequences

The investigation model now has several important properties:

* The Event Log is the source of truth; the Case State is a projection.
* Unknowns, not hypotheses, define investigative scope.
* Evidence remains immutable while interpretations evolve.
* Multiple competing interpretations are preserved until resolved.
* The Hypothesis Graph models reasoning, while the Experiment Dependency Graph models execution.
* Architectural decisions are Decision Events with materialized Decision State, not peer investigative objects.
* Every state change is event-driven and reproducible.
* Large investigations scale through queryable projections rather than distributing the full Case State.

These properties collectively transform the Case State from a passive data structure into an **epistemic model** of the investigation itself.

---

## Judge Review — Part III

**Status:** ✅ Approved. Prior findings resolved.

This chapter establishes a rigorous domain model. The following refinements from the initial review are incorporated:

1. **Decision** is not a first-class investigation object. Decisions are **Decision Events** in the Event Log, with current decision status materialized in Case State.
2. **Information Gain** is deferred to Part IV as a qualitative framework (not numerical scoring).
3. **Arbitration authority** is clarified: the Judge determines whether existing evidence is sufficient or whether additional experimentation is required. The Judge does not decide which interpretation is technically correct.

With these refinements, Part III provides a robust domain model on which the Investigation Orchestrator (Part IV) is built.

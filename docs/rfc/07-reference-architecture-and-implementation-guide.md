# Debugging Engine v3.1

# Part VII — Reference Architecture & Implementation Guide

> **Status:** Informative
>
> This chapter is not part of the normative specification. It presents one possible reference architecture demonstrating how the concepts defined in Parts I–VI can be realized in practice. Implementations MAY differ provided they remain compliant with the normative requirements.

---

# 1. Objectives

The reference implementation has four goals.

1. Demonstrate that the specification is implementable.
2. Provide a baseline architecture for future implementations.
3. Validate that the specification contains no missing concepts.
4. Serve as a testbed for future versions of Debugging Engine.

It is **not** intended to be the only implementation.

---

# 2. High-Level Architecture

```text
                   ┌──────────────────────────┐
                   │        Client UI         │
                   └────────────┬─────────────┘
                                │
                                ▼
                 ┌────────────────────────────┐
                 │     Investigation API      │
                 └────────────┬───────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
      Event Store                  Projection Engine
                │                           │
                ▼                           ▼
          Event Bus                  Case State Store
                │                           │
      ┌─────────┴───────────────────────────┐
      │                                     │
      ▼                                     ▼
 Investigation Orchestrator         Knowledge Service
      │
      ├──────────────┬──────────────┬──────────────┐
      ▼              ▼              ▼              ▼
 Analyst       Adversary      Implementer     Verifier
```

Every component communicates through events and Case State projections.

No agent communicates directly with another agent.

---

# 3. Recommended Repository Layout

```text
debugging-engine/

├── specification/
│   ├── part1-philosophy.md
│   ├── part2-agents.md
│   ├── part3-model.md
│   ├── part4-orchestrator.md
│   ├── part5-learning.md
│   ├── part6-formal.md
│   └── part7-reference.md
│
├── schemas/
│   ├── case.schema.json
│   ├── unknown.schema.json
│   ├── hypothesis.schema.json
│   ├── experiment.schema.json
│   ├── evidence.schema.json
│   └── interpretation.schema.json
│
├── contracts/
│
├── orchestrator/
│
├── agents/
│
├── event-store/
│
├── projections/
│
├── knowledge/
│
├── examples/
│
└── tests/
```

The repository organization mirrors the conceptual architecture.

> **Note:** This repository (`debugging-engine`) stores the specification under `docs/rfc/` rather than `debugging-engine/specification/`. The layout above remains an informative reference for implementations that prefer a different tree.

---

# 4. Suggested Service Boundaries

A production deployment may separate responsibilities into independent services.

| Service            | Responsibility                                               |
| ------------------ | ------------------------------------------------------------ |
| Investigation API  | External interface                                           |
| Event Store        | Persistent event log                                         |
| Projection Service | Materialized Case State                                      |
| Orchestrator       | Scheduling and lifecycle management                          |
| Agent Runtime      | Executes Analyst, Adversary, Implementer, and Verifier tasks |
| Knowledge Service  | Retrieval and validation                                     |
| UI                 | Visualization and interaction                                |

Service decomposition is optional.

Logical responsibilities remain fixed.

---

# 5. Persistence Model

The reference implementation uses Event Sourcing.

```text
Domain Event

↓

Append Event Store

↓

Projection

↓

Case State
```

Case State may be regenerated entirely by replaying events.

This enables:

* complete auditability,
* historical reconstruction,
* debugging of investigations,
* projection evolution.

---

# 6. Example Investigation

Suppose an engineer reports:

> "API latency increased after yesterday's deployment."

### Step 1 – Create Investigation

```
CaseCreated
UnknownDiscovered
```

Unknown:

```
Why did API latency increase?
```

---

### Step 2 – Analyst

Produces hypotheses.

```
Redis contention

Database connection exhaustion

GC pauses
```

Events

```
HypothesisProposed

HypothesisProposed

HypothesisProposed
```

---

### Step 3 – Adversary

Challenges assumptions.

Example

```
Deployment changed logging configuration.

Verbose logging may explain latency.
```

Event

```
HypothesisProposed
```

---

### Step 4 – Judge

Schedules experiments.

```
Collect latency metrics

↓

Collect Redis metrics

↓

Profile GC
```

---

### Step 5 – Implementer

Adds instrumentation.

```
Tracing enabled
```

---

### Step 6 – Verifier

Runs benchmark.

Produces evidence.

```
Redis latency

142 ms
```

EvidenceRecorded

---

### Step 7 – Analyst

Interprets evidence.

```
Supports Redis contention.
```

---

### Step 8 – Adversary

Provides competing interpretation.

```
Database retry storm indirectly caused Redis contention.
```

---

### Step 9 – Judge

Determines existing evidence cannot resolve the disagreement.

Requests a new discriminating experiment.

---

### Step 10 – New Experiment

Disable retry policy.

Observe Redis latency.

---

### Step 11 – Verification

Evidence

```
Redis latency returns to normal.
```

---

### Step 12 – Root Cause

```
Database retry storm

↓

Redis contention

↓

High latency
```

Event

```
RootCauseAccepted
```

---

### Step 13 – Learning

Validated investigation enters Knowledge Repository.

Future investigations retrieve it using fingerprints.

---

# 7. Visualization

A practical implementation SHOULD provide visualizations for:

* Unknown hierarchy
* Hypothesis graph
* Experiment dependency graph
* Timeline of events
* Evidence registry
* Investigation lifecycle
* Knowledge lineage

Visualization is not required for compliance but greatly improves usability.

---

# 8. Performance Considerations

The architecture is designed to scale through:

* event sourcing,
* asynchronous processing,
* query projections,
* parallel experiment execution,
* independent agent runtimes.

Large investigations SHOULD avoid distributing the complete Case State to every agent. Query-based projections remain the preferred mechanism.

---

# 9. Testing Strategy

A conforming implementation should test at multiple levels.

### Unit Tests

* Domain object validation
* State transition rules
* Event validation

### Integration Tests

* Projection correctness
* Event ordering
* Agent contract compliance

### End-to-End Tests

* Complete investigation replay
* Parallel experiment scheduling
* Human escalation flow
* Knowledge validation pipeline

Replay testing is particularly important because it verifies that the Event Log alone is sufficient to reconstruct the investigation.

---

# 10. Evolution Strategy

Debugging Engine is intended to evolve without breaking existing investigations.

Recommended approach:

* Add new event types only through versioned extensions.
* Preserve backward compatibility for object schemas where possible.
* Introduce new projections rather than modifying historical events.
* Record Architecture Decision Records (ADRs) for any change affecting the normative specification.

This allows long-lived investigation histories to remain valid across versions.

---

# 11. Known Limitations

Debugging Engine intentionally leaves several areas open for future work.

* Multi-case investigations that share evidence.
* Distributed orchestration across multiple organizations.
* Formal reasoning about probabilistic systems.
* Automated generation of verification specifications.
* Adaptive scheduling heuristics based on historical outcomes.
* Formal verification of orchestration policies.

These topics are outside the scope of v3.1.

---

# 12. Future Roadmap

A possible evolution path is:

* **v3.2** — Pluggable scheduling policies and richer experiment planning.
* **v3.3** — Cross-investigation reasoning and federated knowledge repositories.
* **v4.0** — Multi-case orchestration, collaborative investigations, and formally verified orchestration semantics.

The philosophy established in Part I should remain stable even as these capabilities expand.

---

# Appendix A — Terminology

The specification concludes with a canonical glossary defining every architectural term—Case State, Unknown, Hypothesis, Experiment, Evidence, Interpretation, Event, Projection, Orchestrator, Information Gain, Verification Specification, Fingerprint, and related concepts. Each term has a single normative definition to eliminate ambiguity across implementations.

---

# Appendix B — Architecture Decision Records (ADRs)

All future changes to the normative specification should be documented as ADRs. Each ADR records:

* Context
* Decision
* Rationale
* Consequences
* Alternatives Considered

This provides a transparent governance process for evolving Debugging Engine while preserving backward compatibility.

---

# Final Judge Review — Debugging Engine v3.1

**Status:** ✅ **Accepted for Publication**

The v3.1 specification now forms a coherent architectural standard rather than a collection of design ideas. The review finds that it successfully:

* Separates **philosophy**, **architecture**, **domain model**, **orchestration**, **execution**, **formal contracts**, and **implementation guidance** into distinct concerns.
* Resolves the primary inconsistencies identified in v3.0, including the Judge's role, numerical confidence, hidden prompt state, and synchronous investigation loops.
* Establishes a complete event-driven investigation model with explicit ownership, immutable evidence, query-based Case State access, and reproducible state transitions.
* Defines clear extension points that allow implementations to vary in technology while preserving interoperability.

## Recommendations for v3.2

Although the specification is publication-ready, several areas would benefit from further research before the next revision:

1. **Formal Scheduling Policies** — The Judge currently relies on qualitative information gain. Future versions could define interchangeable scheduling strategies without introducing numerical confidence.
2. **Case State Query Language** — Standardize a declarative query language for agent projections to improve interoperability.
3. **Knowledge Validation Framework** — Define how organizations measure the long-term usefulness and reliability of learned knowledge.
4. **Distributed Investigations** — Extend the model to investigations spanning multiple repositories, services, or organizations.
5. **Reference Implementation** — Validate the specification by implementing the complete architecture and documenting lessons learned through ADRs.

With these recommendations, Debugging Engine has evolved from an architectural concept into a specification that could realistically serve as the blueprint for a production-grade investigation platform and a basis for independent implementations. The next milestone is no longer further philosophical refinement—it is building and validating the reference implementation against real debugging scenarios.

# Debugging Engine v3.1

# Part IV — Event-Driven Investigation Orchestrator

> **Status:** Normative
>
> This chapter defines how investigations evolve over time. Unlike traditional debugging workflows, Debugging Engine is not iteration-driven or prompt-driven. It is an event-driven orchestration system in which investigation state changes only in response to explicit domain events.

---

# 1. Purpose

The Investigation Orchestrator governs the progression of an investigation.

It answers questions such as:

* What should happen next?
* Which experiments may execute?
* Which experiments must wait?
* Has uncertainty been reduced?
* Has progress stalled?
* Should investigation continue?
* Should a human be involved?

It never answers:

* What is the bug?
* Which hypothesis is technically correct?
* Which implementation is best?

Those remain the responsibility of technical agents and empirical evidence.

---

# 2. Event-Driven Execution

Unlike conventional multi-agent loops,

```text
Think

↓

Reply

↓

Think

↓

Reply
```

Debugging Engine executes through domain events.

```text
Event

↓

State Transition

↓

Scheduling Decision

↓

Agent Invocation

↓

New Event
```

No agent "takes turns."

The orchestrator reacts whenever the investigation state changes.

---

# 3. Event Categories

Every event belongs to one of six categories.

### Investigation Events

Control the lifecycle of the investigation.

Examples:

* CaseCreated
* InvestigationActivated
* InvestigationEscalated
* InvestigationResolved
* InvestigationAbandoned

---

### Discovery Events

Expand the problem space.

Examples:

* UnknownDiscovered
* UnknownResolved
* UnknownReopened

---

### Hypothesis Events

Modify the explanatory model.

Examples:

* HypothesisProposed
* HypothesisPromoted
* HypothesisWeakened
* HypothesisSuspended
* HypothesisRejected

---

### Experiment Events

Represent experiment lifecycle.

Examples:

* ExperimentApproved
* ExperimentScheduled
* ExperimentStarted
* ExperimentCompleted
* ExperimentCancelled
* ExperimentExpired

---

### Evidence Events

Represent new observations.

Examples:

* EvidenceRecorded
* InterpretationSubmitted
* InterpretationWithdrawn

Notice there is intentionally **no** `InterpretationAccepted` event.

Interpretations are not accepted.

Evidence accumulates until a decision can be justified.

---

### Decision Events

Architectural decisions are represented as immutable events.

Examples:

* RootCauseAccepted
* InvestigationEscalated
* InvestigationClosed

The current investigation state is a projection of these events.

---

# 4. Orchestration Cycle

The orchestrator follows a simple invariant.

Every event produces exactly three phases.

```text
Event Arrives

↓

Update Case State

↓

Evaluate Scheduling
```

Nothing else.

The orchestrator never reasons directly.

---

# 5. Scheduling Philosophy

Scheduling is an optimization problem, not a debugging problem.

The Judge optimizes:

* expected uncertainty reduction,
* resource consumption,
* execution safety,
* dependency constraints,
* investigation progress.

The Judge never evaluates technical correctness.

---

# 6. Information Gain

Earlier versions attempted numerical confidence.

Debugging Engine v3.1 replaces this with qualitative Information Gain.

Information Gain estimates how much uncertainty an experiment could remove.

It is not a probability.

It is not confidence.

It is a planning heuristic supplied by the Analyst.

The Analyst classifies proposed experiments into four categories.

| Level   | Meaning                                                                   |
| ------- | ------------------------------------------------------------------------- |
| HIGH    | Could eliminate multiple competing hypotheses or resolve a major Unknown. |
| MEDIUM  | Clarifies one important uncertainty.                                      |
| LOW     | Provides incremental clarification.                                       |
| MINIMAL | Unlikely to materially affect the investigation.                          |

The Judge compares experiments only within these qualitative categories.

No arithmetic is performed.

---

# 7. Experiment Cost

Similarly, execution cost is qualitative.

| Level    | Examples                                                              |
| -------- | --------------------------------------------------------------------- |
| LOW      | Read logs, execute unit tests, inspect metrics.                       |
| MEDIUM   | Build branch, deploy staging, run integration tests.                  |
| HIGH     | Production benchmark, long-running load test, distributed deployment. |
| CRITICAL | Risky production intervention or high operational cost.               |

Cost is supplied by the Analyst and constrained by organizational policy.

---

# 8. Scheduling Matrix

Scheduling combines Information Gain and Cost.

For example:

| Information Gain | Cost     | Typical Action                        |
| ---------------- | -------- | ------------------------------------- |
| HIGH             | LOW      | Execute immediately.                  |
| HIGH             | MEDIUM   | Schedule if dependencies permit.      |
| MEDIUM           | LOW      | Execute when resources are available. |
| LOW              | HIGH     | Defer unless investigation stalls.    |
| MINIMAL          | CRITICAL | Normally reject.                      |

This is a policy framework, not a scoring algorithm.

Organizations MAY customize these policies.

---

# 9. Experiment Dependency Graph

The orchestrator schedules against the Experiment Dependency Graph rather than the Hypothesis Graph.

Dependencies are represented explicitly.

### Ordering dependency

```text
Capture baseline metrics

↓

Modify cache configuration
```

Baseline must complete first.

---

### Resource dependency

```text
Experiment A

↓

Uses staging cluster
```

Experiment B requiring the same exclusive resource must wait.

---

### Interference dependency

```text
Enable verbose logging

×

Latency benchmark
```

Running both simultaneously invalidates results.

They cannot execute concurrently.

---

# 10. Parallel Execution

Experiments MAY execute concurrently only when:

* resource dependencies are satisfied,
* interference constraints are absent,
* ordering constraints are satisfied,
* organizational policy permits.

Parallelism is therefore explicit rather than opportunistic.

---

# 11. Long-Running Experiments

Some investigations require prolonged observation.

Examples:

* memory leaks,
* race conditions,
* intermittent production failures,
* distributed consensus issues.

These experiments remain in the `RUNNING` state until completion criteria are met.

While they execute, the orchestrator MAY continue scheduling unrelated work.

The investigation never blocks on a single experiment.

---

# 12. Arbitration

Competing interpretations are expected.

The orchestrator does **not** determine which interpretation is correct.

Instead it asks a different question:

> **Can the current evidence resolve this disagreement?**

If yes:

* the investigation proceeds.

If no:

* the orchestrator requests new discriminating experiments from the Analyst.

Evidence—not authority—resolves technical disagreements.

---

# 13. Replanning

Every new event may trigger replanning.

Examples:

* an experiment failed unexpectedly,
* evidence weakens the leading hypothesis,
* a new Unknown is discovered,
* a dependency is removed,
* resources become available.

The orchestrator continuously adapts the investigation plan.

There is no concept of a fixed investigation sequence.

---

# 14. Starvation Policy

Investigations must never become permanently idle.

If all executable experiments are deferred because of low information gain or excessive cost, the orchestrator enters a recovery phase.

Possible actions include:

1. Request new experiment proposals from the Analyst.
2. Ask the Adversary to identify overlooked alternatives.
3. Request additional human information.
4. Escalate if no meaningful progress is possible.

Waiting indefinitely is prohibited.

---

# 15. Human Escalation

Escalation is an explicit architectural state.

The orchestrator MUST escalate when any of the following conditions hold:

* No executable experiment can further reduce uncertainty.
* Investigation progress has stalled over a configurable number of scheduling cycles.
* Required information depends on external domain expertise.
* Safety or policy constraints prohibit remaining experiments.
* Critical disagreement cannot be resolved empirically.

Escalation is considered a successful completion of autonomous investigation.

---

# 16. Completion Criteria

An investigation may transition to `RESOLVED` only when all conditions are satisfied:

1. All priority Unknowns are resolved.
2. Verification succeeds.
3. No unresolved critical objections remain.
4. Remaining hypotheses are rejected, suspended, or unsupported.
5. A `RootCauseAccepted` decision event is emitted.
6. Required organizational approval has been obtained (if applicable).

Resolution is therefore a state transition governed by explicit criteria rather than a conversational conclusion.

---

# 17. Architectural Properties

The Event-Driven Investigation Orchestrator provides the following guarantees:

* **Responsiveness:** Any meaningful event may immediately trigger replanning.
* **Concurrency:** Independent experiments proceed without blocking unrelated work.
* **Determinism:** State transitions are driven by explicit events rather than hidden reasoning.
* **Safety:** Dependencies and interference are represented explicitly before scheduling.
* **Auditability:** Every orchestration decision is reconstructible from the Event Log.
* **Scalability:** The orchestrator manages investigations of varying complexity without relying on synchronous reasoning loops.

The orchestrator therefore acts less like a conversational coordinator and more like an operating system scheduler for epistemic work: allocating resources, enforcing constraints, reacting to events, and advancing investigations without participating in technical reasoning itself.

---

# Judge Review — Part IV

**Status:** ✅ Approved with one architectural recommendation.

This chapter successfully transforms Debugging Engine from an iterative prompt workflow into an event-driven orchestration architecture. The separation between technical reasoning and orchestration is now clear, and the Experiment Dependency Graph resolves several shortcomings identified in the v3.0 review.

One refinement is recommended for Part V: the orchestrator currently reacts to events after they occur, but some events (such as long-running experiments or human responses) are inherently asynchronous. Rather than having the orchestrator poll for completion, Part V should define an **Event Bus** as the transport layer through which agents publish domain events. The Investigation Orchestrator would subscribe to these events instead of actively monitoring every experiment. This preserves the event-driven philosophy end-to-end and cleanly separates orchestration logic from execution infrastructure. If adopted, the Event Bus should be treated as infrastructure rather than as a new architectural agent, maintaining the seven-agent model while improving implementation clarity.

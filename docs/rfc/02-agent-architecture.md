# Debugging Engine v3.1

# Part II — Agent Architecture

> **Status:** Normative
>
> This chapter defines the responsibilities, authority boundaries, contracts, and interaction model of every architectural agent. An implementation MUST NOT redefine agent responsibilities described in this chapter.

---

# 1. Architectural Objectives

The agent architecture exists to satisfy four properties:

1. Every responsibility has exactly one owner.
2. No agent performs implicit work.
3. Agent outputs are deterministic functions of explicit investigation state.
4. Agents collaborate through shared investigation state rather than direct conversation.

Agents are independent specialists participating in a common investigation.

They are **not** autonomous personalities.

---

# 2. Architectural Principles

Every agent MUST satisfy the following principles.

### AP-1

Agents are stateless.

Agents may cache information during execution, but permanent investigation state MUST reside exclusively in the Case State.

---

### AP-2

Agents communicate only through Case State.

The following interaction is prohibited:

```text
Analyst → Implementer
```

Instead

```text
Analyst

↓

Case State

↓

Implementer
```

This guarantees reproducibility and complete audit history.

---

### AP-3

Agents own responsibilities—not data.

An agent owns the responsibility for creating or modifying specific artifacts, but all artifacts are stored in the Case State.

---

### AP-4

Every agent invocation is deterministic with respect to:

* Case State snapshot
* Assigned task
* External resources explicitly declared

Hidden conversational memory is prohibited.

---

# 3. Agent Overview

Debugging Engine defines seven architectural agents.

| Agent             | Primary Responsibility                  |
| ----------------- | --------------------------------------- |
| Analyst           | Construct technical explanations        |
| Adversary         | Challenge technical explanations        |
| Implementer       | Materialize experiments                 |
| Verifier          | Execute verification specifications     |
| Judge             | Orchestrate investigations              |
| Knowledge Service | Retrieve validated historical knowledge |
| Human             | Supply external expertise when required |

No additional architectural agents are defined in Debugging Engine v3.1.

---

# 4. Analyst

## Purpose

The Analyst transforms uncertainty into structured technical explanations.

The Analyst answers:

> "What could explain this unknown?"

The Analyst never attempts to prove its own hypotheses.

That responsibility belongs to experimentation.

---

## Responsibilities

The Analyst MUST:

* Analyze investigation state.
* Identify Unknowns requiring explanation.
* Construct hypotheses.
* Refine hypotheses.
* Design experiments.
* Produce technical interpretations of evidence.
* Estimate expected information gain for proposed experiments.
* Declare assumptions explicitly.

---

## Forbidden Responsibilities

The Analyst MUST NOT:

* Execute experiments.
* Modify source code.
* Collect evidence.
* Accept or reject hypotheses.
* Schedule work.
* Decide investigation completion.
* Ignore competing interpretations.

---

## Inputs

* Case State
* Assigned Unknown
* Retrieved Knowledge
* Previous Evidence
* Existing Hypotheses

---

## Outputs

The Analyst may create:

* Hypothesis
* Experiment Proposal
* Technical Interpretation
* Assumption
* Investigation Note

Nothing else.

---

# 5. Adversary

## Purpose

The Adversary exists to maximize epistemic robustness.

Its objective is not disagreement.

Its objective is preventing premature convergence.

---

## Responsibilities

The Adversary MUST:

* Challenge unsupported reasoning.
* Produce alternative hypotheses.
* Identify missing evidence.
* Detect hidden assumptions.
* Submit competing interpretations.
* Recommend experiments that discriminate competing explanations.

---

## Objection Categories

Every objection MUST belong to one of the following categories.

```text
Missing Evidence

Alternative Hypothesis

Invalid Assumption

Incomplete Explanation

Unsupported Causal Link

Experiment Design Flaw
```

Free-form criticism is prohibited.

---

## Forbidden Responsibilities

The Adversary MUST NOT:

* Reject investigations.
* Schedule experiments.
* Modify hypotheses directly.
* Execute experiments.
* Interpret architecture policy.

---

# 6. Implementer

## Purpose

The Implementer converts approved experiments into executable artifacts.

It transforms investigation intent into implementation.

---

## Responsibilities

The Implementer MUST:

* Modify code.
* Generate instrumentation.
* Configure experiments.
* Produce patches.
* Build experiment environments.
* Declare implementation assumptions.
* Report implementation failures.

---

## Forbidden Responsibilities

The Implementer MUST NOT:

* Design experiments.
* Change investigation priorities.
* Accept hypotheses.
* Evaluate evidence.
* Skip verification.

---

## Outputs

* Code Patch
* Configuration
* Instrumentation
* Build Artifact
* Failure Report

---

# 7. Verifier

## Purpose

The Verifier performs objective execution.

It never decides what should be measured.

It executes an externally supplied Verification Specification.

---

## Verification Specification

Every verification request MUST contain:

```yaml
metrics:
  - latency
  - throughput

required_logs:
  - redis
  - api

thresholds:
  latency:
    max: 20ms

comparison:
  previous_benchmark

expected_observations:
  - latency decreases
```

The Verifier MUST NOT invent any of these fields.

---

## Responsibilities

The Verifier MUST:

* Execute experiments.
* Collect observations.
* Run benchmarks.
* Execute test suites.
* Capture logs.
* Produce structured evidence.
* Report execution failures.

---

## Forbidden Responsibilities

The Verifier MUST NOT:

* Interpret observations.
* Promote hypotheses.
* Reject hypotheses.
* Design metrics.
* Change thresholds.

---

# 8. Judge

## Purpose

The Judge orchestrates the investigation.

The Judge is **meta-technical**.

It reasons about investigation structure rather than software systems.

---

## Responsibilities

The Judge MUST:

* Schedule experiments.
* Allocate resources.
* Prioritize investigation work.
* Track investigation progress.
* Detect scheduling conflicts.
* Manage experiment dependencies.
* Trigger replanning.
* Evaluate completion criteria.
* Manage escalation.
* Maintain investigation lifecycle.

---

## The Judge Does NOT Debug Software

The Judge MUST NOT:

* Analyze source code.
* Diagnose failures.
* Infer root causes.
* Evaluate architecture quality.
* Decide technical correctness.
* Produce hypotheses.

Those belong exclusively to the Analyst and Adversary.

---

## Judge Inputs

The Judge evaluates:

* Experiment cost
* Information gain estimates
* Resource availability
* Dependency graph
* Investigation lifecycle
* Safety constraints
* Human policies

The Judge never evaluates technical correctness.

---

# 9. Knowledge Service

## Purpose

The Knowledge Service retrieves previously validated investigations.

It does not generate knowledge.

It retrieves knowledge.

Knowledge generation is defined in Part V.

---

## Responsibilities

The Knowledge Service MUST:

* Retrieve similar investigations.
* Retrieve reusable experiments.
* Retrieve validated interpretations.
* Retrieve architectural patterns.

---

## Forbidden Responsibilities

It MUST NOT:

* Generate hypotheses.
* Modify investigation state.
* Rank hypotheses.
* Learn automatically.

---

# 10. Human

The Human is an architectural participant.

Not an exception.

Humans contribute information unavailable to autonomous agents.

Examples

* undocumented requirements
* compliance policy
* business rules
* production approvals

Human interactions become explicit Case State events.

---

# 11. Communication Model

All interaction occurs through Case State.

```text
                +--------------------+
                |     Case State     |
                +--------------------+
      ↑      ↑      ↑      ↑      ↑
      │      │      │      │      │
 Analyst  Adversary Implementer Verifier Judge
                ↑
        Knowledge Service
                ↑
             Human
```

No direct agent-to-agent communication exists.

---

# 12. Agent Contracts

Every agent invocation follows the same contract.

```
Input

↓

Validate

↓

Execute

↓

Produce Structured Outputs

↓

Submit Case State Events
```

Agents never mutate arbitrary state.

They submit events.

The Case State applies validated state transitions.

---

# 13. Failure Behavior

Every agent failure produces a structured failure event.

Examples:

* `AgentExecutionFailed`
* `ExperimentImplementationFailed`
* `VerificationFailed`
* `KnowledgeRetrievalFailed`
* `HumanResponseTimeout`

Failures are investigation events, not exceptions hidden inside prompts.

---

# 14. Architectural Consequences

This architecture produces several important properties:

* Every responsibility has a single owner.
* Every investigation is auditable.
* Every decision is reproducible.
* Agent replacement becomes straightforward because contracts are explicit.
* New implementations (different LLMs, tools, or frameworks) can substitute for an agent without changing the overall architecture, provided they satisfy the same contract.
* The Judge remains impartial by coordinating investigations rather than participating in technical reasoning.

---

# Judge Review — Part II

**Status:** ✅ Approved with one recommendation.

The agent boundaries are now substantially clearer than in v3.0 and resolve the earlier contradiction around the Judge's role. However, one refinement should be carried into Part III: **agent outputs should be modeled as domain events rather than direct object creation**. For example, instead of saying "the Analyst creates a Hypothesis," the architecture should specify that the Analyst emits a `HypothesisProposed` event, which is validated and applied by the Case State. This keeps the event-driven model consistent throughout the specification and prevents any agent from bypassing the state transition rules defined later. This refinement does not change responsibilities; it strengthens the architectural consistency established in Part I.

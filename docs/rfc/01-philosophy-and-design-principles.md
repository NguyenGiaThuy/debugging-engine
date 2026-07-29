# Debugging Engine v3.1

# Part I — Philosophy & Design Principles

> **Status:** Normative
>
> This chapter defines the immutable principles of Debugging Engine. Every subsequent chapter MUST conform to this chapter. If any later chapter contradicts this chapter, this chapter takes precedence.

---

# 1. Introduction

Software debugging is fundamentally an epistemic process. Developers begin with incomplete knowledge of a system's behavior and progressively reduce uncertainty through observation, experimentation, and reasoning until a sufficiently validated explanation emerges.

Large Language Models have significantly improved the ability to generate explanations, propose code changes, and automate routine engineering tasks. However, most existing agentic debugging systems remain centered on conversational reasoning rather than structured investigation. They frequently optimize for producing plausible answers instead of systematically reducing uncertainty.

Debugging Engine (State Machine–Driven Agentic Debugging Workflow) proposes a different approach.

Rather than treating debugging as a sequence of prompts exchanged between autonomous agents, Debugging Engine models debugging as a stateful, event-driven investigation in which explicit representations of uncertainty, hypotheses, experiments, evidence, and decisions govern the behavior of every agent.

Agents are not responsible for "finding the answer."

Agents are responsible for advancing the investigation.

---

# 2. Motivation

Modern multi-agent systems often exhibit several recurring failure modes.

## 2.1 Hypothesis Lock-in

The first plausible explanation quickly becomes the dominant explanation.

Subsequent reasoning attempts to defend it rather than challenge it.

Alternative explanations receive progressively less attention despite insufficient evidence.

---

## 2.2 Prompt-Centric Reasoning

Important investigation state exists only inside prompts.

For example

```
We already tried X.

Y seemed unlikely.

Let's remember that...
```

None of this exists as explicit machine-readable state.

Consequences include

* forgotten context
* repeated work
* inconsistent reasoning
* difficult auditing
* poor reproducibility

---

## 2.3 Implicit Decision Making

Critical decisions such as

* abandoning hypotheses
* prioritizing experiments
* accepting root causes

are frequently hidden inside generated text.

The system cannot explain

why

a decision occurred.

---

## 2.4 Weak Separation of Responsibilities

Many architectures assign overlapping responsibilities to multiple agents.

One agent proposes a fix.

Another evaluates it.

A third also evaluates it.

A fourth silently modifies it.

Responsibility becomes ambiguous.

When an investigation fails, ownership is unclear.

---

## 2.5 Conversation Instead of Investigation

Conversations are excellent for exchanging ideas.

Investigations require

* explicit state
* reproducible decisions
* measurable progress
* evidence management
* revision history

Debugging Engine therefore models debugging as an investigation rather than a conversation.

---

# 3. Architectural Vision

Debugging Engine views debugging as an iterative process of uncertainty reduction.

The objective of an investigation is not to maximize confidence in a hypothesis.

The objective is to minimize unresolved uncertainty.

Every architectural decision supports this goal.

Reasoning proposes possibilities.

Experiments generate observations.

Observations constrain explanations.

Validated explanations become decisions.

---

# 4. Core Design Principles

The following principles define the philosophical foundation of Debugging Engine.

These principles are normative.

---

## Principle 1 — Structured Observations Constrain Reasoning

Reasoning is necessary but insufficient.

Reasoning generates explanations.

Structured, reproducible observations determine whether those explanations survive.

No hypothesis may advance solely because it appears persuasive.

Every promotion requires supporting evidence.

---

## Principle 2 — Unknowns Drive Investigation

Traditional debugging often begins with hypotheses.

Debugging Engine begins with unknowns.

Examples include

* Why is latency increasing?
* Why does the service restart?
* Why does memory continue growing?
* Why is authentication failing?

Hypotheses exist only to explain unknowns.

When an unknown is resolved, the investigation progresses.

---

## Principle 3 — State Must Be Explicit

Every meaningful artifact of an investigation MUST exist as structured state.

This includes

* unknowns
* hypotheses
* experiments
* evidence
* interpretations
* decisions

Reasoning hidden inside prompts has no architectural meaning.

---

## Principle 4 — Responsibilities Must Be Exclusive

Every responsibility has exactly one owner.

Ownership must never be ambiguous.

For example

The Analyst constructs explanations.

The Adversary challenges explanations.

The Verifier performs measurements.

The Judge coordinates investigations.

No responsibility is shared.

---

## Principle 5 — Observation and Interpretation Are Different

An observation is something that occurred.

An interpretation is an explanation of why it occurred.

Example

Observation

```
Redis latency increased from 8 ms to 140 ms.
```

Interpretation A

```
Redis lock contention caused the slowdown.
```

Interpretation B

```
Database retries indirectly saturated Redis.
```

Both interpretations explain the same observation.

Therefore observations and interpretations are modeled separately.

---

## Principle 6 — Every Decision Must Be Traceable

Every architectural decision must answer

* What evidence supported this?
* Which competing explanations were considered?
* Which experiments produced the evidence?
* Who made the decision?
* When was the decision made?

If these questions cannot be answered, the decision is architecturally invalid.

---

## Principle 7 — Investigations Are Event-Driven

Debugging Engine does not execute fixed reasoning loops.

Instead, investigations evolve through events.

Examples include

* New hypothesis proposed
* Experiment completed
* Evidence recorded
* Human feedback received
* Budget exhausted

Each event may alter investigation state.

The investigation advances because state changes—not because another prompt was generated.

---

## Principle 8 — Human Expertise Is Part of the Architecture

Human escalation is not evidence of failure.

Some uncertainty cannot be reduced autonomously.

Examples include

* undocumented business rules
* compliance constraints
* production-only behavior
* organizational policy

Escalating under these conditions is correct behavior.

---

## Principle 9 — Architecture Before Implementation

The architecture defines behavior.

Implementation realizes behavior.

Implementation must never redefine architecture.

This specification therefore prioritizes

* formal models
* explicit state
* contracts
* schemas
* state machines

before discussing implementation technologies.

---

# 5. Non-Goals

Debugging Engine intentionally does not attempt to solve every engineering problem.

It is **not**

* a prompt engineering framework,
* a software development lifecycle,
* a project management methodology,
* an issue tracking system,
* a replacement for version control,
* a universal autonomous software engineer.

Its scope is autonomous investigation and debugging.

---

# 6. Design Consequences

The principles above lead to several unavoidable architectural consequences.

1. Every investigation must maintain explicit state.
2. Every state transition must be observable.
3. Every experiment must have a defined objective.
4. Every hypothesis must be evidence-backed.
5. Every agent must have exclusive responsibilities.
6. Every decision must be reproducible.
7. Every reusable lesson must undergo validation before entering the knowledge base.
8. The system must know when autonomous investigation is no longer justified.

These are not implementation choices; they are architectural requirements.

---

# 7. Success Criteria

An implementation conforms to Debugging Engine if it can demonstrate the following properties:

* Investigations are represented as explicit, versioned state.
* Agents interact only through the Case State.
* The Judge orchestrates investigations without performing technical analysis.
* Hypotheses advance only through structured evidence.
* Competing interpretations are preserved until resolved.
* Experiments are managed through explicit lifecycle states.
* Human escalation follows defined guard conditions.
* Completed investigations are reproducible from recorded events.
* Every architectural concept is formally specified through schemas and contracts.

An implementation that satisfies these criteria is considered Debugging Engine–compliant, regardless of programming language, LLM provider, orchestration framework, or deployment environment.

---

## Judge Review — Part I

**Status:** ✅ Approved with no findings.

This chapter establishes a coherent philosophical foundation for the remainder of the specification. It resolves the numerical confidence contradiction, explicitly distinguishes observations from interpretations, formalizes the event-driven nature of investigations, and defines immutable architectural principles without introducing implementation details. Subsequent chapters are now constrained by these principles and may not redefine them without an Architecture Decision Record (ADR).

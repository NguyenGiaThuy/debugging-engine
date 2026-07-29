# SMADW v3.1 — RFC Index

**Version:** 3.1  
**Project:** [reasoning-engine](../../README.md)

## Status legend

| Status | Meaning |
| --- | --- |
| **Normative** | Required for SMADW compliance. Implementations MUST satisfy these requirements. |
| **Informative** | Guidance and examples. Implementations MAY differ provided normative parts are satisfied. |

## Precedence

1. If any later chapter contradicts [Part I](01-philosophy-and-design-principles.md), Part I takes precedence unless the change is recorded in an Architecture Decision Record (ADR).
2. No later chapter may introduce new first-class investigation objects without updating [Part III](03-investigation-model.md).
3. [Part VII](07-reference-architecture-and-implementation-guide.md) is non-binding and does not redefine normative contracts.

## Table of contents

| Part | Title | File | Status |
| --- | --- | --- | --- |
| I | Philosophy & Design Principles | [01-philosophy-and-design-principles.md](01-philosophy-and-design-principles.md) | Normative |
| II | Agent Architecture | [02-agent-architecture.md](02-agent-architecture.md) | Normative |
| III | Investigation Model | [03-investigation-model.md](03-investigation-model.md) | Normative |
| IV | Event-Driven Investigation Orchestrator | [04-event-driven-investigation-orchestrator.md](04-event-driven-investigation-orchestrator.md) | Normative |
| V | Execution, Verification & Learning | [05-execution-verification-and-learning.md](05-execution-verification-and-learning.md) | Normative |
| VI | Formal Specification | [06-formal-specification.md](06-formal-specification.md) | Normative |
| VII | Reference Architecture & Implementation Guide | [07-reference-architecture-and-implementation-guide.md](07-reference-architecture-and-implementation-guide.md) | Informative |

## Reading order

Parts I–VI define **what SMADW is**. Part VII demonstrates **how SMADW can be built**. Readers implementing a compliant system should treat Parts I–VI as the contract and Part VII as one possible realization.

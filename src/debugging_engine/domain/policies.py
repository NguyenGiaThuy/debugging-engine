"""Phase 2 architectural constants (see docs/decisions/)."""

from __future__ import annotations

# ADR 0002 — Hypothesis budget
MAX_ACTIVE_HYPOTHESES_PER_UNKNOWN = 5

# ADR 0001 — Evidence / projection size
MAX_OBSERVATION_CHARS = 2048
MAX_PROJECTION_FIELD_CHARS = 160

# ADR 0003 — Scheduling cycle escalation
STALL_CYCLES_BEFORE_ESCALATION = 5

# Terminal / inactive hypothesis statuses (do not count toward budget)
INACTIVE_HYPOTHESIS_STATUSES = frozenset({"REJECTED", "SUSPENDED", "ACCEPTED"})

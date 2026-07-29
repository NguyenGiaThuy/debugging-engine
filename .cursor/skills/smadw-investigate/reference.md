# SMADW reference (for agents)

## CLI

| Command | Purpose |
| --- | --- |
| `smadw open <issue.md>` | CaseCreated + UnknownDiscovered |
| `smadw next <case-id>` | Judge Task JSON |
| `smadw query <case-id> [slice]` | Projection (`summary`, `hypotheses`, …) |
| `smadw submit <case-id> --events file.json` | Append domain events |
| `smadw verify <case-id> <experiment-id>` | Run Verification Spec |
| `smadw status` / `log` / `replay` | Inspect |
| `smadw demo` | Stub e2e (offline) |
| `smadw validate` | Phase 2 architectural scenarios |

Install: `pip install -e ".[dev]"` (or `uv pip install -e ".[dev]"`).

## Event envelope

Every submitted event needs:

```json
{
  "case_id": "<uuid>",
  "event_type": "HypothesisProposed",
  "timestamp": "2026-07-29T12:00:00Z",
  "producer": "Analyst",
  "schema_version": "3.1.0",
  "payload": {}
}
```

`event_id`, `correlation_id` may be omitted (kernel generates defaults).

## Common payloads

### HypothesisProposed

```json
{
  "id": "<uuid>",
  "unknown_id": "<uuid>",
  "title": "short title",
  "explanation": "technical explanation",
  "assumptions": ["..."]
}
```

### ExperimentProposed

```json
{
  "id": "<uuid>",
  "unknown_id": "<uuid>",
  "title": "Reproduce failing tests",
  "information_gain": "HIGH",
  "cost": "LOW",
  "affected_hypotheses": ["<hyp-id>"],
  "expected_observations": ["tests fail before fix"],
  "experiment_class": "observational",
  "verification_spec": {
    "command": ["python", "-m", "pytest", "path/to/tests", "-q"],
    "expected_exit_code": 0,
    "working_directory": "."
  },
  "patch": null
}
```

For interventions, set `"experiment_class": "intervention"` and optional `"patch": {"relative/path.py": "file contents"}`.

### ExperimentApproved

```json
{ "experiment_id": "<uuid>", "authority": "Judge" }
```

### InterpretationSubmitted

```json
{
  "id": "<uuid>",
  "evidence_id": "<uuid>",
  "hypothesis_id": "<uuid>",
  "outcome": "SUPPORTS",
  "rationale": "why"
}
```

`outcome`: `SUPPORTS` | `WEAKENS` | `INCONCLUSIVE`.

### RootCauseAccepted

```json
{
  "hypothesis_id": "<uuid>",
  "rationale": "evidence-backed explanation",
  "authority": "Judge"
}
```

### InvestigationEscalated

```json
{ "reason": "why autonomous investigation cannot continue" }
```

## Qualitative levels

- Information gain: `HIGH` | `MEDIUM` | `LOW` | `MINIMAL`
- Cost: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`
- Reject `MINIMAL` + `CRITICAL` experiments; propose better ones.

## Objection categories (Adversary)

`Missing Evidence` | `Alternative Hypothesis` | `Invalid Assumption` | `Incomplete Explanation` | `Unsupported Causal Link` | `Experiment Design Flaw`

## Policies (Phase 2)

- Max **5** active hypotheses per Unknown.
- Evidence observations truncated (~2 KiB).
- Stall cycles → Judge asks to escalate.

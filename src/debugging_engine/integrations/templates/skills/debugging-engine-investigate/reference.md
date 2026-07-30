# Debugging Engine reference (for agents)

## CLI

| Command | Purpose |
| --- | --- |
| `debugging-engine open <issue.md>` | CaseCreated + UnknownDiscovered |
| `debugging-engine next <case-id>` | Judge Task JSON |
| `debugging-engine query <case-id> [slice]` | Projection (`summary`, `hypotheses`, …) |
| `debugging-engine submit <case-id> --events file.json` | Append domain events |
| `debugging-engine verify <case-id> <experiment-id>` | Run Verification Spec |
| `debugging-engine status` / `log` / `replay` | Inspect |
| `debugging-engine demo` | Stub e2e (offline) |
| `debugging-engine validate` | Phase 2 architectural scenarios |

Install: `uv tool install debugging-engine --from git+https://github.com/NguyenGiaThuy/debugging-engine` (or `uv pip install -e ".[dev]"` for local development).

## Event envelope

Every submitted event needs:

```json
{
  "case_id": "<uuid>",
  "event_type": "HypothesisProposed",
  "timestamp": "2026-07-29T12:00:00Z",
  "producer": "Analyst",
  "schema_version": "1.0.0",
  "payload": {}
}
```

`event_id`, `correlation_id` may be omitted (kernel generates defaults).

**Producer:** must equal the current Judge Task `role` (e.g. do not submit `producer: "Adversary"` while the Task role is Analyst). Event `schema_version` is currently `"1.0.0"` (envelope schema), independent of the PyPI package version.

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

Optional `"parent_id": "<hyp-id>"` links a child hypothesis (same Unknown; rejecting the parent rejects descendants).

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

Patch map keys and `working_directory` must be relative paths **inside** the repo (no `..` segments, no absolute paths). Escaping paths are rejected at propose/verify time.

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

After new SUPPORTS evidence, Judge typically schedules an **Adversary** rebuttal before the next approve/accept.

### Skills: investigate vs incident

| Skill | Mode | Interventions / Implementer |
| --- | --- | --- |
| `debugging-engine-investigate` | Report-only | **Forbidden.** Accept root cause on observational evidence; write `issues/<slug>.md`; fix later via incident. |
| `debugging-engine-incident` | Fix | **Allowed.** Propose `experiment_class=intervention` + `patch`, Implementer, verify, then accept. |

### RootCauseAccepted

```json
{
  "hypothesis_id": "<uuid>",
  "rationale": "evidence-backed explanation",
  "authority": "Judge"
}
```

Kernel gates (all required):

- Producer and `authority` are **Judge**
- At least one SUPPORTS interpretation for `hypothesis_id`, linked to recorded evidence
- Every piece of evidence from a terminal experiment (COMPLETED/FAILED) has an interpretation
- At least one verification with `passed: true` and experiment COMPLETED
- If any intervention/patched experiment exists, one of them must have passed
- Competing hypotheses are rejected or suspended

Investigate (report-only) must not create intervention experiments, so the intervention gate does not apply.

### InvestigationEscalated

```json
{ "reason": "why autonomous investigation cannot continue" }
```

## Verify outcomes

`debugging-engine verify` runs the Verification Spec. Unexpected exit codes record evidence and mark the experiment **FAILED** (not COMPLETED). Interpret that evidence, then propose the next experiment.

## Qualitative levels

- Information gain: `HIGH` | `MEDIUM` | `LOW` | `MINIMAL`
- Cost: `LOW` | `MEDIUM` | `HIGH` | `CRITICAL`
- Reject `MINIMAL` + `CRITICAL` experiments; propose better ones.

## Objection categories (Adversary)

`Missing Evidence` | `Alternative Hypothesis` | `Invalid Assumption` | `Incomplete Explanation` | `Unsupported Causal Link` | `Experiment Design Flaw`

Adversary `HypothesisProposed` and `InterpretationSubmitted` events **must** include `"objection_category"` with one of the values above.

## Policies (Phase 2)

- Max **5** active hypotheses per Unknown.
- Evidence observations truncated (~2 KiB).
- Stall cycles → Judge asks to escalate.
- One Judge Task at a time (Spec §10 parallel execution is not implemented in the package).
- After SUPPORTS with no pending intervention, Judge may accept root cause (report-only). Propose an intervention only when running the **incident** skill.

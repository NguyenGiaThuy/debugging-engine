# Verify path escape and experiment lifecycle inconsistencies

## Symptoms
Static review of `src/debugging_engine` found concrete integrity issues that the current suite (45 passing tests) does not cover:

1. **Patch path traversal in verification** (`infrastructure/verify.py`): experiment patches are written via `repo_root / rel_path` with no containment check. Paths like `../outside.txt` or absolute paths can write outside the repo.
2. **Working directory escape**: `VerificationSpec.working_directory` is joined the same way and can run subprocesses outside the repo.
3. **Failed verification still completes**: on unexpected exit code the verifier emits `VerificationFailed` then always emits `ExperimentCompleted`. `ExperimentStatus.FAILED` exists in the model but is never reached.
4. **RootCauseAccepted under-validated**: accepting a root cause only requires an existing hypothesis + rationale; no evidence, competing-hypothesis disposition, or successful verification is required (contradicts SPECIFICATION.md acceptance gates).
5. **Non-atomic batch submit**: `append_many` validates/writes event-by-event; a mid-batch failure leaves partial events on disk.

## Success criteria
- Path containment rejects `../` and absolute patch/cwd paths under verify.
- Failed verification leaves the experiment in a failed/non-completed terminal state (or documents intentional COMPLETED+VerificationFailed semantics and removes unused FAILED status).
- RootCauseAccepted rejects acceptance without supporting evidence / required preconditions from the spec (or spec is explicitly weakened with tests).
- Regression tests cover the above; suite still green.

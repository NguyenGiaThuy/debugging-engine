# SMADW investigate examples

## Seeded cache bug

```bash
smadw open subject/issues/001-cache-miss.md
# note case_id
smadw next <case-id>
```

Typical path:

1. Analyst proposes asymmetric key normalization + observational experiment (pytest).
2. Adversary proposes an alternative hypothesis.
3. Judge approves experiment → `smadw verify`.
4. Interpret evidence; propose intervention with patch if needed.
5. Verify fix; `RootCauseAccepted`.

Offline proof: `smadw demo`.

## New issue file

Create `subject/issues/002-whatever.md`:

```markdown
# Short unknown title

## Symptoms
...

## Success criteria
pytest path passes / metric recovers
```

Then `smadw open subject/issues/002-whatever.md` and follow `next`.

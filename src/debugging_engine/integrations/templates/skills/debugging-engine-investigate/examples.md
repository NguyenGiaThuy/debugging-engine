# Debugging Engine investigate examples

## Offline demo

```bash
debugging-engine demo
```

Runs a stub investigation against a temporary cache-miss fixture (no LLM).

## New issue file

Create `issues/002-whatever.md` (or any path):

```markdown
# Short unknown title

## Symptoms
...

## Success criteria
pytest path passes / metric recovers
```

Then:

```bash
debugging-engine open issues/002-whatever.md
debugging-engine next <case-id>
```

Follow the Judge task: reason/edit outside the kernel, `submit` events, `verify` when scheduled.

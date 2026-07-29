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

Follow the Judge task for the assigned role only, then `submit` allowed events, then immediately `next` again. Run `verify` only when the Task role is Verifier (after Judge approval). Analyst proposes experiments as events — does not self-approve or implement.

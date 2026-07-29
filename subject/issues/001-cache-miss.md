# Cache lookups miss for mixed-case keys

## Symptoms

After storing a value with key `User`, a subsequent lookup with `User` or `user` returns `None`.

Lowercase-only keys appear to work.

## Suspected area

`subject/cache.py` — key handling in `Cache.set` / `Cache.get`.

## Success criteria

`pytest subject/tests/test_cache.py` passes, including mixed-case roundtrips.

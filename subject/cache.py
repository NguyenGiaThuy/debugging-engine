"""Tiny in-memory cache used as the SMADW investigation subject."""


def normalize_key(key: str) -> str:
    # BUG: unused on set path — get lowercases, set does not.
    return key.strip().lower()


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        # BUG: stores raw key without normalization
        self._store[key] = value

    def get(self, key: str) -> object | None:
        return self._store.get(key.lower())

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._store

"""In-memory session store used as a Debugging Engine investigation subject.

Sessions should stay alive while clients keep calling ``touch()`` within the TTL.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class Session:
    session_id: str
    created_at: float
    last_seen: float
    user_id: str


class SessionStore:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, Session] = {}

    def create(self, session_id: str, user_id: str, *, now: float | None = None) -> Session:
        t = monotonic() if now is None else now
        session = Session(
            session_id=session_id,
            created_at=t,
            last_seen=t,
            user_id=user_id,
        )
        self._sessions[session_id] = session
        return session

    def touch(self, session_id: str, *, now: float | None = None) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        t = monotonic() if now is None else now
        # Activity is recorded...
        session.last_seen = t
        return session

    def is_active(self, session_id: str, *, now: float | None = None) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        t = monotonic() if now is None else now
        # BUG: expiry is computed from created_at, ignoring touch()/last_seen.
        # Idle sessions that were refreshed still expire relative to creation time.
        return (t - session.created_at) <= self._ttl

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

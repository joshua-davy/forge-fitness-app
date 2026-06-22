"""Small in-process rate limiter for sensitive local Forge endpoints.

Hosted multi-worker Forge must replace this with Redis or another shared store.
Keeping the limiter here still prevents rapid credential guessing in the local
and single-instance deployment path.
"""
from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, status

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def enforce_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
    now = monotonic()
    with _lock:
        attempts = _attempts[key]
        while attempts and attempts[0] <= now - window_seconds:
            attempts.popleft()
        if len(attempts) >= limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts. Wait a few minutes before trying again.",
            )
        attempts.append(now)

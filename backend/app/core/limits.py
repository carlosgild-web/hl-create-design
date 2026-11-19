"""Public-demo safety: a per-IP rate limiter (in memory, one process) and client IP lookup.

The limiter is a sliding window. It protects the demo from a script hammering the
assistant (each chat turn costs model tokens); it is not a security boundary.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from functools import lru_cache

WINDOW_S = 60.0
MAX_KEYS = 10_000  # bound the memory of the table when many different IPs show up


class RateLimiter:
    def __init__(self, limit: int, *, window_s: float = WINDOW_S, clock=time.monotonic) -> None:
        self.limit, self.window_s, self._clock = limit, window_s, clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> int | None:
        """Count one request. Returns None if allowed, else seconds to wait."""
        now = self._clock()
        if len(self._hits) > MAX_KEYS:
            self._prune(now)
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, int(self.window_s - (now - hits[0])) + 1)
        hits.append(now)
        return None

    def _prune(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window_s]:
            del self._hits[key]


@lru_cache
def get_limiter(limit: int) -> RateLimiter:
    """One limiter per process and limit value (tests clear the cache)."""
    return RateLimiter(limit)


def client_ip(peer: str | None, forwarded_for: str | None, *, trust_forwarded: bool) -> str:
    """The caller's address. `X-Forwarded-For` is only believed behind a proxy we run;
    then its last entry is the one our proxy appended (earlier ones the client can fake)."""
    if trust_forwarded and forwarded_for:
        last = forwarded_for.split(",")[-1].strip()
        if last:
            return last
    return peer or "unknown"


Clock = Callable[[], float]

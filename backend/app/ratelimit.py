"""Small in-memory sliding-window limiter for public endpoints. Single-process only (documented)."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)


def limit(name: str, max_calls: int, per_seconds: int):
    def dep(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"{name}:{ip}"
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > per_seconds:
            q.popleft()
        if len(q) >= max_calls:
            raise HTTPException(429, "Too many requests. Please slow down and try again shortly.")
        q.append(now)

    return dep


def reset():
    _hits.clear()

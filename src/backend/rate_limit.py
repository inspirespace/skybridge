from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, window_seconds: int, max_events: int) -> None:
    """Internal helper for init  ."""
        self._window = window_seconds
        self._max = max_events
        self._events: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
    """Handle allow."""
        now = time.time()
        window_start = now - self._window
        bucket = self._events.get(key)
        if bucket is None:
            bucket = deque()
            self._events[key] = bucket
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True

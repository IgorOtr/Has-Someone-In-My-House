"""A minimal in-memory sliding-window rate limiter.

Process-local state only (no Redis/external store) — adequate for a
single-instance local dashboard, not meant to survive restarts or multiple
server processes.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class InMemoryRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be greater than 0.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0.")
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Record an attempt for ``key`` and return whether it is within limits."""
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] > self._window_seconds:
                attempts.popleft()
            if len(attempts) >= self._max_attempts:
                return False
            attempts.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()

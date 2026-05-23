"""Simple in-memory fixed-window rate limiter."""

from collections import deque
from threading import Lock
from time import time


class InMemoryRateLimiter:
    """Thread-safe fixed-window limiter for small deployments."""

    def __init__(self):
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Returns: (allowed, retry_after_seconds)
        """
        now = time()
        window_start = now - float(window_seconds)

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= int(max_requests):
                retry_after = int(max(1, window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0

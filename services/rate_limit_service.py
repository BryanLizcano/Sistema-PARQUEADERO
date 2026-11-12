from collections import deque
import os
import threading
import time


class LoginRateLimiter:
    """Limitador ligero en memoria por ventana deslizante para proteger /api/auth/login."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _current_limits(self) -> tuple[int, int]:
        max_attempts = int(os.getenv("LOGIN_RATE_LIMIT_MAX", str(self.max_attempts)))
        window_seconds = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW", str(self.window_seconds)))
        return max_attempts, window_seconds

    def check_and_record(self, key: str) -> tuple[bool, int]:
        max_attempts, window_seconds = self._current_limits()
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            if len(self._attempts) > 1024:
                self._prune_empty(cutoff)

            bucket = self._attempts.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_attempts:
                retry_after = max(1, int(bucket[0] + window_seconds - now) + 1)
                return False, retry_after

            bucket.append(now)
            return True, 0

    def _prune_empty(self, cutoff: float) -> None:
        stale_keys = []
        for k, bucket in self._attempts.items():
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                stale_keys.append(k)
        for k in stale_keys:
            del self._attempts[k]

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter()

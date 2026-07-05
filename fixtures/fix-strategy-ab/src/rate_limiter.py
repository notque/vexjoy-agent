"""Token-bucket rate limiter. Bug: wrong comparison operator allows one extra request."""

import time


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, max_tokens: int, refill_rate: float):
        """max_tokens: bucket capacity. refill_rate: tokens per second."""
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def try_acquire(self) -> bool:
        """Return True if a token is available, consuming it."""
        self._refill()
        # BUG: >= should be >, allowing acquire when tokens == 0
        if self.tokens >= 0:
            self.tokens -= 1
            return True
        return False

"""LRU cache with TTL. Bug: expired entries are returned instead of evicted."""

import time


class TTLCache:
    """Fixed-size cache with time-to-live expiry."""

    def __init__(self, max_size: int, ttl_seconds: float):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        """Return cached value or None if missing/expired."""
        if key not in self._store:
            return None
        timestamp, value = self._store[key]
        # BUG: should check if entry is expired and evict it, but returns stale value
        return value

    def put(self, key: str, value: object) -> None:
        """Store a value. Evicts oldest entry if at capacity."""
        if len(self._store) >= self.max_size and key not in self._store:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic(), value)

    def size(self) -> int:
        """Return number of entries (including expired)."""
        return len(self._store)

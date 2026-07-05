"""Tests for cache — the critical test targets expired entry returns."""

import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.cache import TTLCache


def test_basic_get_put():
    c = TTLCache(max_size=10, ttl_seconds=60)
    c.put("k", "v")
    assert c.get("k") == "v"


def test_expired_entry_returns_none():
    """After TTL expires, get() must return None, not stale data."""
    c = TTLCache(max_size=10, ttl_seconds=0.5)
    c.put("k", "v")
    # Simulate time passing beyond TTL
    with patch("src.cache.time") as mock_time:
        # Put happened at monotonic=100
        c._store["k"] = (100.0, "v")
        # Now it's 101 (1 second later, TTL is 0.5)
        mock_time.monotonic.return_value = 101.0
        assert c.get("k") is None


def test_missing_key():
    c = TTLCache(max_size=10, ttl_seconds=60)
    assert c.get("nonexistent") is None


def test_eviction_at_capacity():
    c = TTLCache(max_size=2, ttl_seconds=60)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # should evict oldest
    assert c.size() == 2

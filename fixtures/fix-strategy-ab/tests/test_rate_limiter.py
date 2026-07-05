"""Tests for rate_limiter — the critical test targets the >= vs > bug."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.rate_limiter import RateLimiter


def test_allows_up_to_max():
    rl = RateLimiter(max_tokens=3, refill_rate=0)
    assert rl.try_acquire() is True
    assert rl.try_acquire() is True
    assert rl.try_acquire() is True


def test_blocks_after_max():
    """After max_tokens acquires with zero refill, next acquire must fail."""
    rl = RateLimiter(max_tokens=2, refill_rate=0)
    rl.try_acquire()
    rl.try_acquire()
    assert rl.try_acquire() is False


def test_single_token():
    rl = RateLimiter(max_tokens=1, refill_rate=0)
    assert rl.try_acquire() is True
    assert rl.try_acquire() is False

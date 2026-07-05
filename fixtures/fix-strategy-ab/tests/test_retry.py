"""Tests for retry — the critical test targets the zero-multiplier bug."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.retry import retry


def test_succeeds_first_try():
    call_count = 0

    @retry(max_attempts=3)
    def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    assert succeed() == "ok"
    assert call_count == 1


def test_default_backoff_is_nonzero():
    """Default retry() must produce non-zero delays between attempts."""
    delays = []

    @retry(max_attempts=3)
    def always_fail():
        raise ValueError("fail")

    with patch("src.retry.time.sleep", side_effect=delays.append):
        try:
            always_fail()
        except ValueError:
            pass

    # With base_delay=1.0 and a working multiplier, delays should be > 0
    assert len(delays) == 2  # 3 attempts = 2 sleeps
    assert all(d > 0 for d in delays), f"Expected nonzero delays, got {delays}"

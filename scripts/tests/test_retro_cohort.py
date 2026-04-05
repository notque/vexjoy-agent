"""Tests for scripts/retro-cohort-gate.py cohort assignment logic."""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading — retro-cohort-gate.py has hyphens in filename
# ---------------------------------------------------------------------------

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "retro-cohort-gate.py"


def _load_module():
    """Load retro-cohort-gate.py as a Python module via importlib.

    Returns:
        Loaded module object.
    """
    spec = importlib.util.spec_from_file_location("retro_cohort_gate", str(_SCRIPT_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
should_inject = _mod.should_inject


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hex_session(value: int) -> str:
    """Create a 32-char hex session ID with a known 8-char prefix.

    Args:
        value: Integer to place in the first 8 hex digits.

    Returns:
        32-character hex string.
    """
    prefix = format(value, "08x")
    return prefix + "0" * 24


# ---------------------------------------------------------------------------
# Known-value tests
# ---------------------------------------------------------------------------


class TestKnownValues:
    """Tests against session IDs with pre-computed cohort values."""

    def test_odd_prefix_returns_true(self):
        """int('00000001', 16) == 1, which is odd → inject."""
        session_id = _hex_session(0x00000001)
        assert should_inject(session_id) is True

    def test_even_prefix_returns_false(self):
        """int('00000002', 16) == 2, which is even → no inject."""
        session_id = _hex_session(0x00000002)
        assert should_inject(session_id) is False

    def test_zero_prefix_returns_false(self):
        """int('00000000', 16) == 0, which is even → no inject."""
        session_id = _hex_session(0x00000000)
        assert should_inject(session_id) is False

    def test_large_odd_prefix_returns_true(self):
        """int('ffffffff', 16) == 4294967295, which is odd → inject."""
        session_id = _hex_session(0xFFFFFFFF)
        assert should_inject(session_id) is True

    def test_large_even_prefix_returns_false(self):
        """int('fffffcfe', 16) == 4294966526, which is even → no inject."""
        session_id = _hex_session(0xFFFFFCFE)
        assert should_inject(session_id) is False

    @pytest.mark.parametrize(
        "hex_prefix,expected",
        [
            ("00000003", True),  # 3 is odd
            ("0000000a", False),  # 10 is even
            ("0000000f", True),  # 15 is odd
            ("deadbeef", True),  # 3735928559 is odd
            ("cafebabe", False),  # 3405691582 is even
        ],
    )
    def test_parametrized_known_values(self, hex_prefix: str, expected: bool):
        """Verify parametrised known prefix → expected inject value.

        Args:
            hex_prefix: 8-char hex prefix to use.
            expected: Expected return value of should_inject.
        """
        session_id = hex_prefix + "0" * 24
        assert should_inject(session_id) is expected


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Verify that the same session_id always returns the same result."""

    def test_same_id_returns_same_result_true(self):
        """Odd-prefix ID returns True consistently across multiple calls."""
        session_id = _hex_session(0x00000001)
        results = [should_inject(session_id) for _ in range(10)]
        assert all(r is True for r in results)

    def test_same_id_returns_same_result_false(self):
        """Even-prefix ID returns False consistently across multiple calls."""
        session_id = _hex_session(0x00000002)
        results = [should_inject(session_id) for _ in range(10)]
        assert all(r is False for r in results)

    def test_different_ids_can_differ(self):
        """Consecutive IDs (odd/even) produce different results."""
        odd_id = _hex_session(0x00000001)
        even_id = _hex_session(0x00000002)
        assert should_inject(odd_id) != should_inject(even_id)


# ---------------------------------------------------------------------------
# Stderr output tests
# ---------------------------------------------------------------------------


class TestStderrOutput:
    """Verify stderr logging messages."""

    def test_stderr_on_for_odd(self, capsys: pytest.CaptureFixture):
        """Odd-prefix session logs 'retro-cohort: on' to stderr.

        Args:
            capsys: Pytest capture fixture.
        """
        session_id = _hex_session(0x00000001)
        should_inject(session_id)
        captured = capsys.readouterr()
        assert "retro-cohort: on" in captured.err

    def test_stderr_off_for_even(self, capsys: pytest.CaptureFixture):
        """Even-prefix session logs 'retro-cohort: off' to stderr.

        Args:
            capsys: Pytest capture fixture.
        """
        session_id = _hex_session(0x00000002)
        should_inject(session_id)
        captured = capsys.readouterr()
        assert "retro-cohort: off" in captured.err

    def test_stderr_contains_retro_cohort_label(self, capsys: pytest.CaptureFixture):
        """Stderr always contains the 'retro-cohort:' prefix.

        Args:
            capsys: Pytest capture fixture.
        """
        for value in [0x00000001, 0x00000002]:
            should_inject(_hex_session(value))
        captured = capsys.readouterr()
        assert captured.err.count("retro-cohort:") == 2


# ---------------------------------------------------------------------------
# Distribution test
# ---------------------------------------------------------------------------


class TestDistribution:
    """Verify that ~50% of random hex strings are assigned to treatment."""

    def test_roughly_half_inject_in_random_sample(self, capsys: pytest.CaptureFixture):
        """100 random hex session IDs should yield 35-65% True (treatment).

        Args:
            capsys: Pytest capture fixture (absorbs stderr noise).
        """
        rng = random.Random(42)  # deterministic seed for reproducibility
        session_ids = [format(rng.getrandbits(128), "032x") for _ in range(100)]
        results = [should_inject(sid) for sid in session_ids]
        true_count = sum(1 for r in results if r is True)
        assert 35 <= true_count <= 65, f"Expected ~50% True, got {true_count}/100"

    def test_distribution_with_sequential_ids(self, capsys: pytest.CaptureFixture):
        """Sequential IDs 0-99 should produce exactly 50 True values.

        Args:
            capsys: Pytest capture fixture.
        """
        results = [should_inject(_hex_session(i)) for i in range(100)]
        true_count = sum(1 for r in results if r is True)
        # Odd numbers in 0..99: exactly 50
        assert true_count == 50

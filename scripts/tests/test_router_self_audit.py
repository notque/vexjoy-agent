"""Unit tests for scripts/router-self-audit.py helpers.

The audit script shells to four other scripts; those have their own tests.
Here we pin the pure pieces: the pytest-summary parser and the replay
test-file list (a renamed file would silently shrink the audited suite).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
audit = importlib.import_module("router-self-audit")


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("148 passed in 12.30s", (148, 0)),
        ("2 failed, 146 passed in 11.02s", (146, 2)),
        ("1 error in 0.10s", (0, 1)),
        ("1 failed, 1 error, 10 passed in 2.00s", (10, 2)),
        ("no tests ran in 0.01s", (0, 0)),
        ("", (0, 0)),
    ],
)
def test_parse_pytest_counts(output: str, expected: tuple[int, int]) -> None:
    """Summary tokens parse into (passed, failed+errors)."""
    assert audit.parse_pytest_counts(output) == expected


def test_replay_test_files_exist() -> None:
    """Every audited replay test file exists — a rename must update the audit."""
    for rel in audit.REPLAY_TEST_FILES:
        assert (REPO_ROOT / rel).is_file(), f"replay test file missing: {rel}"

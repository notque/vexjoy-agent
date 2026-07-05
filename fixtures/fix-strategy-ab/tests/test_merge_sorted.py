"""Tests for merge_sorted — the critical test targets remainder draining."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.merge_sorted import merge_sorted


def test_equal_length():
    assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]


def test_unequal_length():
    """Longer list's remainder must be included in the result."""
    assert merge_sorted([1, 2, 3, 4, 5], [6]) == [1, 2, 3, 4, 5, 6]


def test_empty_first():
    assert merge_sorted([], [1, 2, 3]) == [1, 2, 3]


def test_empty_second():
    assert merge_sorted([1, 2], []) == [1, 2]


def test_both_empty():
    assert merge_sorted([], []) == []

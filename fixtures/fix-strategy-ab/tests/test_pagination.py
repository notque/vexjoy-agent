"""Tests for pagination — the critical test targets the off-by-one."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pagination import get_page, paginate


def test_exact_division():
    assert paginate(list(range(10)), 5) == 2


def test_remainder_needs_extra_page():
    """10 items at page_size=3 needs 4 pages, not 3."""
    assert paginate(list(range(10)), 3) == 4


def test_single_item():
    assert paginate([1], 5) == 1


def test_empty():
    assert paginate([], 5) == 0


def test_get_page_basic():
    items = list(range(1, 11))
    assert get_page(items, 1, 3) == [1, 2, 3]
    assert get_page(items, 4, 3) == [10]

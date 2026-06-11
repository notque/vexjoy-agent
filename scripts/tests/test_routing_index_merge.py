"""Tests for scripts/routing_index_merge.py and its three importers.

Invariants:
1. routing-manifest.py, pre-route.py, and index-router.py share one merge —
   identical output for the same tracked + local inputs.
2. A stale local file never hides newly added tracked entries (PR #778).
3. A stale local never overrides tracked content (force_route, triggers);
   local fills gaps per-name only.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

ROUTING_MODULES = ["routing-manifest", "pre-route", "index-router"]


@pytest.fixture
def merge(monkeypatch: pytest.MonkeyPatch):
    """Import the shared merge module."""
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    return importlib.import_module("routing_index_merge")


@pytest.fixture
def routing_modules(monkeypatch: pytest.MonkeyPatch) -> list:
    """Import the three routing scripts (hyphenated names need importlib)."""
    monkeypatch.syspath_prepend(str(SCRIPTS_DIR))
    return [importlib.import_module(name) for name in ROUTING_MODULES]


def _write_indexes(tmp_path: Path, tracked: dict, local: dict | None) -> Path:
    """Write tracked INDEX.json (and optional INDEX.local.json); return tracked path."""
    tracked_path = tmp_path / "INDEX.json"
    tracked_path.write_text(json.dumps(tracked), encoding="utf-8")
    if local is not None:
        (tmp_path / "INDEX.local.json").write_text(json.dumps(local), encoding="utf-8")
    return tracked_path


# ---------------------------------------------------------------------------
# Invariant 1: one merge across all three entry points
# ---------------------------------------------------------------------------


def test_all_three_scripts_use_shared_merge(merge, routing_modules):
    """Each script's _load_index_items IS the shared function — divergence impossible."""
    for mod in routing_modules:
        assert mod._load_index_items is merge.load_index_items, mod.__name__


def test_identical_output_across_entry_points(tmp_path, routing_modules):
    """Same tracked + local inputs produce identical merged output everywhere."""
    tracked_path = _write_indexes(
        tmp_path,
        {"skills": {"a": {"triggers": ["t1"]}, "b": {"force_route": True}}},
        {"skills": {"a": {"triggers": ["stale"]}, "priv": {"triggers": ["p"]}}},
    )
    results = [mod._load_index_items(tracked_path, "INDEX.local.json", "skills") for mod in routing_modules]
    assert results[0] == results[1] == results[2]
    assert set(results[0]) == {"a", "b", "priv"}


# ---------------------------------------------------------------------------
# Invariant 2: stale local never hides new tracked entries (PR #778)
# ---------------------------------------------------------------------------


def test_stale_local_does_not_hide_new_tracked_entries(tmp_path, merge):
    tracked_path = _write_indexes(
        tmp_path,
        {"skills": {"old": {"triggers": ["o"]}, "brand-new": {"triggers": ["n"]}}},
        {"skills": {"old": {"triggers": ["o"]}}},  # stale: predates brand-new
    )
    items = merge.load_index_items(tracked_path, "INDEX.local.json", "skills")
    assert "brand-new" in items


# ---------------------------------------------------------------------------
# Invariant 3: local fills gaps only; tracked content wins per-name
# ---------------------------------------------------------------------------


def test_local_never_overrides_tracked_content(tmp_path, merge):
    tracked_path = _write_indexes(
        tmp_path,
        {"skills": {"s": {"triggers": ["fresh"], "force_route": True}}},
        {"skills": {"s": {"triggers": ["stale"], "force_route": False}}},
    )
    items = merge.load_index_items(tracked_path, "INDEX.local.json", "skills")
    assert items["s"] == {"triggers": ["fresh"], "force_route": True}


def test_local_adds_missing_names_only(tmp_path, merge):
    tracked_path = _write_indexes(
        tmp_path,
        {"agents": {"tracked-only": {"triggers": ["t"]}}},
        {"agents": {"private-only": {"triggers": ["p"]}}},
    )
    items = merge.load_index_items(tracked_path, "INDEX.local.json", "agents")
    assert items == {"tracked-only": {"triggers": ["t"]}, "private-only": {"triggers": ["p"]}}


# ---------------------------------------------------------------------------
# Edge cases preserved from the original copies
# ---------------------------------------------------------------------------


def test_no_local_name_reads_tracked_only(tmp_path, merge):
    tracked_path = _write_indexes(tmp_path, {"pipelines": {"p": {"triggers": []}}}, None)
    items = merge.load_index_items(tracked_path, None, "pipelines")
    assert items == {"p": {"triggers": []}}


def test_missing_local_file_is_ignored(tmp_path, merge):
    tracked_path = _write_indexes(tmp_path, {"skills": {"s": {}}}, None)
    items = merge.load_index_items(tracked_path, "INDEX.local.json", "skills")
    assert items == {"s": {}}


def test_unreadable_or_invalid_files_are_skipped(tmp_path, merge):
    tracked_path = tmp_path / "INDEX.json"
    tracked_path.write_text("not json", encoding="utf-8")
    (tmp_path / "INDEX.local.json").write_text(json.dumps({"skills": {"l": {}}}), encoding="utf-8")
    items = merge.load_index_items(tracked_path, "INDEX.local.json", "skills")
    assert items == {"l": {}}


def test_non_dict_section_is_ignored(tmp_path, merge):
    tracked_path = _write_indexes(tmp_path, {"skills": ["not", "a", "dict"]}, None)
    assert merge.load_index_items(tracked_path, None, "skills") == {}

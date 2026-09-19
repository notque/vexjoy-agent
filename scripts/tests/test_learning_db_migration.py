"""Tests for learning_db_v2 schema migrations.

Covers: harness_runs table creation (v13), record_harness_run() insert,
and schema version correctness.
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

HOOKS_LIB = str(((__import__("pathlib")).Path(__file__).resolve().parents[2] / "hooks" / "lib"))
if HOOKS_LIB not in sys.path:
    sys.path.insert(0, HOOKS_LIB)


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """Point learning_db_v2 at a fresh temp directory and reset module state."""
    import importlib

    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))

    # Force re-import to reset _initialized flag
    if "learning_db_v2" in sys.modules:
        del sys.modules["learning_db_v2"]
    import learning_db_v2

    learning_db_v2._initialized = False
    return learning_db_v2


def test_harness_runs_table_exists(fresh_db):
    """init_db creates the harness_runs table."""
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "harness_runs" in tables


def test_schema_version_is_14(fresh_db):
    """A fresh DB reaches schema version 14."""
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 14


def test_record_harness_run_inserts(fresh_db):
    """record_harness_run inserts a row and returns True."""
    ok = fresh_db.record_harness_run(
        run_id="test-run-001",
        program="fixture_forecast",
        round=1,
        lever="top_k_signals",
        variant="k=5",
        metric_accuracy=0.72,
        metric_brier=0.21,
        kept=True,
        reason="dev improved +0.03",
        dev_size=100,
        baseline_accuracy=0.69,
        baseline_brier=0.24,
    )
    assert ok is True

    with fresh_db.get_connection() as conn:
        row = conn.execute("SELECT * FROM harness_runs WHERE run_id = 'test-run-001'").fetchone()
    assert row is not None
    assert row["program"] == "fixture_forecast"
    assert row["round"] == 1
    assert row["lever"] == "top_k_signals"
    assert row["variant"] == "k=5"
    assert row["kept"] == 1
    assert abs(row["metric_accuracy"] - 0.72) < 1e-6
    assert abs(row["metric_brier"] - 0.21) < 1e-6
    assert row["dev_size"] == 100


def test_record_harness_run_minimal(fresh_db):
    """record_harness_run works with only required fields."""
    ok = fresh_db.record_harness_run(
        run_id="test-run-002",
        program="minimal",
        round=0,
        lever="baseline",
        variant="none",
        kept=False,
    )
    assert ok is True

    with fresh_db.get_connection() as conn:
        row = conn.execute("SELECT * FROM harness_runs WHERE run_id = 'test-run-002'").fetchone()
    assert row is not None
    assert row["kept"] == 0
    assert row["metric_accuracy"] is None
    assert row["metric_brier"] is None


def test_migration_from_v12(fresh_db):
    """Migration from v12 adds harness_runs and v14 columns without breaking existing tables."""
    # Create a DB at v12 (no harness_runs, no v14 columns)
    with fresh_db.get_connection() as conn:
        conn.execute("PRAGMA user_version = 12")
        conn.commit()

    # Reset and re-init to trigger migration
    fresh_db._initialized = False
    fresh_db.init_db()

    with fresh_db.get_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        # v14 columns present on jev_calls
        cols = [c[1] for c in conn.execute("PRAGMA table_info(jev_calls)").fetchall()]
    assert version == 14
    assert "harness_runs" in tables
    # Other tables still present
    assert "learnings" in tables
    assert "jev_calls" in tables
    # v14 columns
    assert "payload_hash" in cols
    assert "answers_json" in cols
    assert "cached" in cols

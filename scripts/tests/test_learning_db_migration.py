"""Tests for learning_db_v2 schema migrations.

Covers harness telemetry, intent-alignment telemetry, and schema migrations.
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

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    return learning_db_v2


def test_harness_runs_table_exists(fresh_db):
    """init_db creates the harness_runs table."""
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "harness_runs" in tables


def test_schema_version_is_16(fresh_db):
    """A fresh DB reaches schema version 16."""
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 16


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
    """Migration from v12 adds later telemetry without breaking existing tables."""
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
    assert version == 16
    assert "harness_runs" in tables
    assert "jev_intent_alignments" in tables
    # Other tables still present
    assert "learnings" in tables
    assert "jev_calls" in tables
    # v14 columns
    assert "payload_hash" in cols
    assert "answers_json" in cols
    assert "cached" in cols


def test_record_and_aggregate_intent_alignments(fresh_db):
    """Proposed-intent rates exclude baseline and unavailable judgments."""
    common = dict(
        transport="vercel-ai-gateway",
        model="typesafe-ai/jev",
        alignment="aligned",
        questions_version="d-intent-v1",
    )
    assert fresh_db.record_jev_intent_alignment(phase="baseline", materially_differs=True, **common)
    assert fresh_db.record_jev_intent_alignment(phase="proposed", materially_differs=False, **common)
    assert fresh_db.record_jev_intent_alignment(
        phase="proposed", materially_differs=True, route_mismatch=False, **common
    )
    assert fresh_db.record_jev_intent_alignment(
        phase="proposed",
        transport="vercel-ai-gateway",
        model="typesafe-ai/jev",
        alignment="unavailable",
        materially_differs=None,
        questions_version="d-intent-v1",
    )
    rows = fresh_db.jev_intent_alignment_stats(1)
    assert len(rows) == 1
    row = rows[0]
    assert row["phase"] == "proposed"
    assert row["judgments"] == 3
    assert row["measured_differences"] == 2
    assert row["material_differences"] == 1
    assert row["material_difference_rate"] == 0.5


def test_intent_alignment_window_compares_iso_timestamps_as_datetimes(fresh_db):
    """ISO 8601 T/+00:00 timestamps must not be compared lexically to SQLite text."""
    common = dict(
        phase="proposed",
        transport="vercel-ai-gateway",
        model="typesafe-ai/jev",
        alignment="aligned",
        materially_differs=False,
    )
    assert fresh_db.record_jev_intent_alignment(ts="2000-01-01T00:00:00+00:00", **common)
    assert fresh_db.record_jev_intent_alignment(ts="2999-01-01T00:00:00+00:00", **common)

    rows = fresh_db.jev_intent_alignment_stats(1)

    assert len(rows) == 1
    assert rows[0]["judgments"] == 1


def test_migration_from_v14_adds_intent_alignment_table(fresh_db):
    """A v14 database gains the append-only intent-alignment table."""
    with fresh_db.get_connection() as conn:
        conn.executescript(fresh_db._SCHEMA.replace(fresh_db._JEV_INTENT_ALIGNMENTS_DDL, ""))
        conn.execute("DROP TABLE IF EXISTS jev_intent_alignments")
        conn.execute("PRAGMA user_version = 14")
        conn.commit()
    fresh_db._initialized = False
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jev_intent_alignments)")}
    assert version == 16
    assert {
        "model",
        "agent_model",
        "agent_effort",
        "agent_runtime",
        "transport",
        "materially_differs",
        "questions_version",
    } <= columns


def test_repairs_preliminary_v15_intent_alignment_schema(fresh_db):
    """A development-era v15 table gains final receipt columns."""
    with fresh_db.get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS jev_intent_alignments")
        conn.executescript(fresh_db._JEV_INTENT_ALIGNMENTS_DDL.replace("    questions_version TEXT,\n", ""))
        conn.execute("PRAGMA user_version = 15")
        conn.commit()
    fresh_db._initialized = False
    fresh_db.init_db()
    with fresh_db.get_connection() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jev_intent_alignments)")}
    assert "questions_version" in columns

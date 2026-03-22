"""Tests for learning ROI tracking in learning-db.py.

Covers table creation, record-activation, record-waste, record-session,
and the roi report (both human-readable and JSON output).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure repo hooks/lib takes priority over ~/.claude/hooks/lib (which may be stale).
# learning-db.py inserts ~/.claude/hooks/lib at sys.path[0], so we must force-reload
# learning_db_v2 from the repo copy after the CLI module import.
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")

# Import the CLI module under test
sys_path_entry = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, sys_path_entry)
learning_db = importlib.import_module("learning-db")
sys.path.pop(0)

# Force-reload learning_db_v2 from the repo (not from ~/.claude/hooks/lib)
sys.path.insert(0, _repo_hooks_lib)
if "learning_db_v2" in sys.modules:
    del sys.modules["learning_db_v2"]
import learning_db_v2 as _ld2_repo

# Patch the CLI module's references to point to the repo version
for attr_name in dir(_ld2_repo):
    if hasattr(learning_db, attr_name) and not attr_name.startswith("__"):
        try:
            setattr(learning_db, attr_name, getattr(_ld2_repo, attr_name))
        except (AttributeError, TypeError):
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point learning DB to a temp directory so tests never touch real data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    # Reset the module-level _initialized flag so init_db() runs fresh each test
    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)

    return db_dir


def _ns(**kwargs: object) -> argparse.Namespace:
    """Build a minimal namespace for command functions."""
    return argparse.Namespace(**kwargs)


def _get_conn(isolated_db: Path) -> sqlite3.Connection:
    """Get a connection to the test database."""
    conn = sqlite3.connect(isolated_db / "learning.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------


class TestTableCreation:
    """Verify new tables are created during init."""

    def test_activations_table_exists(self, isolated_db: Path) -> None:
        from learning_db_v2 import init_db

        init_db()
        conn = _get_conn(isolated_db)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "activations" in tables

    def test_session_stats_table_exists(self, isolated_db: Path) -> None:
        from learning_db_v2 import init_db

        init_db()
        conn = _get_conn(isolated_db)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "session_stats" in tables

    def test_activations_columns(self, isolated_db: Path) -> None:
        from learning_db_v2 import init_db

        init_db()
        conn = _get_conn(isolated_db)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(activations)").fetchall()}
        conn.close()
        assert {"id", "topic", "key", "session_id", "timestamp", "outcome"} <= columns

    def test_session_stats_columns(self, isolated_db: Path) -> None:
        from learning_db_v2 import init_db

        init_db()
        conn = _get_conn(isolated_db)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(session_stats)").fetchall()}
        conn.close()
        assert {"id", "session_id", "had_retro_knowledge", "failure_count", "waste_tokens", "created_at"} <= columns


# ---------------------------------------------------------------------------
# record-activation
# ---------------------------------------------------------------------------


class TestRecordActivation:
    """Test the record-activation subcommand."""

    def test_inserts_activation(self, isolated_db: Path) -> None:
        args = _ns(topic="routing", key="force-route-fix", session="sess-001", outcome="success")
        learning_db.cmd_record_activation(args)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM activations WHERE session_id = 'sess-001'").fetchone()
        conn.close()

        assert row is not None
        assert row["topic"] == "routing"
        assert row["key"] == "force-route-fix"
        assert row["outcome"] == "success"

    def test_multiple_activations_same_session(self, isolated_db: Path) -> None:
        for key in ["fix-a", "fix-b", "fix-c"]:
            args = _ns(topic="debugging", key=key, session="sess-002", outcome="success")
            learning_db.cmd_record_activation(args)

        conn = _get_conn(isolated_db)
        count = conn.execute("SELECT COUNT(*) FROM activations WHERE session_id = 'sess-002'").fetchone()[0]
        conn.close()
        assert count == 3

    def test_activation_with_failure_outcome(self, isolated_db: Path) -> None:
        args = _ns(topic="go-testing", key="table-driven", session="sess-003", outcome="failure")
        learning_db.cmd_record_activation(args)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT outcome FROM activations WHERE session_id = 'sess-003'").fetchone()
        conn.close()
        assert row["outcome"] == "failure"


# ---------------------------------------------------------------------------
# record-waste
# ---------------------------------------------------------------------------


class TestRecordWaste:
    """Test the record-waste subcommand."""

    def test_creates_session_stats_on_first_waste(self, isolated_db: Path) -> None:
        args = _ns(session="sess-w1", tokens=1500)
        learning_db.cmd_record_waste(args)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM session_stats WHERE session_id = 'sess-w1'").fetchone()
        conn.close()

        assert row is not None
        assert row["failure_count"] == 1
        assert row["waste_tokens"] == 1500

    def test_upserts_on_second_waste(self, isolated_db: Path) -> None:
        args1 = _ns(session="sess-w2", tokens=1000)
        learning_db.cmd_record_waste(args1)

        args2 = _ns(session="sess-w2", tokens=500)
        learning_db.cmd_record_waste(args2)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM session_stats WHERE session_id = 'sess-w2'").fetchone()
        conn.close()

        assert row["failure_count"] == 2
        assert row["waste_tokens"] == 1500

    def test_different_sessions_independent(self, isolated_db: Path) -> None:
        learning_db.cmd_record_waste(_ns(session="sess-w3a", tokens=200))
        learning_db.cmd_record_waste(_ns(session="sess-w3b", tokens=800))

        conn = _get_conn(isolated_db)
        row_a = conn.execute("SELECT waste_tokens FROM session_stats WHERE session_id = 'sess-w3a'").fetchone()
        row_b = conn.execute("SELECT waste_tokens FROM session_stats WHERE session_id = 'sess-w3b'").fetchone()
        conn.close()

        assert row_a["waste_tokens"] == 200
        assert row_b["waste_tokens"] == 800


# ---------------------------------------------------------------------------
# record-session
# ---------------------------------------------------------------------------


class TestRecordSession:
    """Test the record-session subcommand."""

    def test_creates_session_stats_entry(self, isolated_db: Path) -> None:
        args = _ns(session="sess-rs1", had_retro=True, failures=2, waste_tokens=3000)
        learning_db.cmd_record_session_stats(args)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM session_stats WHERE session_id = 'sess-rs1'").fetchone()
        conn.close()

        assert row is not None
        assert row["had_retro_knowledge"] == 1
        assert row["failure_count"] == 2
        assert row["waste_tokens"] == 3000

    def test_updates_existing_session(self, isolated_db: Path) -> None:
        args1 = _ns(session="sess-rs2", had_retro=False, failures=1, waste_tokens=500)
        learning_db.cmd_record_session_stats(args1)

        args2 = _ns(session="sess-rs2", had_retro=True, failures=3, waste_tokens=2000)
        learning_db.cmd_record_session_stats(args2)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM session_stats WHERE session_id = 'sess-rs2'").fetchone()
        conn.close()

        # Second call should overwrite
        assert row["had_retro_knowledge"] == 1
        assert row["failure_count"] == 3
        assert row["waste_tokens"] == 2000

    def test_no_retro_flag(self, isolated_db: Path) -> None:
        args = _ns(session="sess-rs3", had_retro=False, failures=0, waste_tokens=0)
        learning_db.cmd_record_session_stats(args)

        conn = _get_conn(isolated_db)
        row = conn.execute("SELECT * FROM session_stats WHERE session_id = 'sess-rs3'").fetchone()
        conn.close()

        assert row["had_retro_knowledge"] == 0


# ---------------------------------------------------------------------------
# ROI report
# ---------------------------------------------------------------------------


def _seed_sessions(
    isolated_db: Path,
    with_retro: int,
    without_retro: int,
    retro_failures: int = 1,
    no_retro_failures: int = 3,
    waste: int = 1000,
) -> None:
    """Seed session_stats with test data for ROI computation."""
    from learning_db_v2 import init_db

    init_db()
    conn = _get_conn(isolated_db)

    for i in range(with_retro):
        conn.execute(
            "INSERT INTO session_stats (session_id, had_retro_knowledge, failure_count, waste_tokens, created_at) VALUES (?, 1, ?, ?, datetime('now'))",
            (f"retro-{i}", retro_failures, waste),
        )

    for i in range(without_retro):
        conn.execute(
            "INSERT INTO session_stats (session_id, had_retro_knowledge, failure_count, waste_tokens, created_at) VALUES (?, 0, ?, ?, datetime('now'))",
            (f"noretro-{i}", no_retro_failures, waste),
        )

    conn.commit()
    conn.close()


def _seed_activations(isolated_db: Path, entries: list[tuple[str, str, int]]) -> None:
    """Seed activations table. entries = [(topic, key, count), ...]."""
    from learning_db_v2 import init_db

    init_db()
    conn = _get_conn(isolated_db)

    for topic, key, count in entries:
        for j in range(count):
            conn.execute(
                "INSERT INTO activations (topic, key, session_id, timestamp, outcome) VALUES (?, ?, ?, datetime('now'), 'success')",
                (topic, key, f"act-sess-{topic}-{key}-{j}"),
            )

    conn.commit()
    conn.close()


def _seed_learnings(isolated_db: Path, entries: list[tuple[str, str]]) -> None:
    """Seed learnings table with topic/key pairs for dead weight testing."""
    from learning_db_v2 import init_db, record_learning

    init_db()
    for topic, key in entries:
        record_learning(topic=topic, key=key, value=f"test value for {topic}/{key}", category="design")


class TestRoiInsufficientData:
    """ROI with fewer than 3 sessions per cohort shows warning."""

    def test_insufficient_with_retro(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=2, without_retro=5)
        args = _ns(json=False)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        assert "Insufficient data" in output

    def test_insufficient_without_retro(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=1)
        args = _ns(json=False)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        assert "Insufficient data" in output

    def test_insufficient_both(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=0, without_retro=0)
        args = _ns(json=False)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        assert "Insufficient data" in output


class TestRoiSufficientData:
    """ROI with enough data computes correctly."""

    def test_computes_improvement(self, isolated_db: Path) -> None:
        # 5 retro sessions with 1 failure each, 5 non-retro with 3 failures each
        _seed_sessions(isolated_db, with_retro=5, without_retro=5, retro_failures=1, no_retro_failures=3)

        from learning_db_v2 import init_db

        init_db()
        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        assert data["sufficient_data"] is True
        assert data["rate_with_retro"] == 1.0
        assert data["rate_without_retro"] == 3.0
        # Improvement: (3.0 - 1.0) / 3.0 * 100 = 66.7%
        assert data["improvement_pct"] == pytest.approx(66.7, abs=0.1)

    def test_estimated_savings(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=4, without_retro=4, retro_failures=1, no_retro_failures=4, waste=2000)

        from learning_db_v2 import init_db

        init_db()
        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        assert data["estimated_savings"] is not None
        assert data["estimated_savings"] > 0

    def test_human_output_contains_rates(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5, retro_failures=1, no_retro_failures=3)
        args = _ns(json=False)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out

        assert "=== Learning ROI Report ===" in output
        assert "failures/session" in output
        assert "Improvement:" in output

    def test_zero_failures_both_cohorts(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5, retro_failures=0, no_retro_failures=0)

        from learning_db_v2 import init_db

        init_db()
        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        # rate_without_retro is 0, so improvement can't be computed (division by zero guard)
        assert data["improvement_pct"] is None


# ---------------------------------------------------------------------------
# ROI --json
# ---------------------------------------------------------------------------


class TestRoiJson:
    """ROI --json produces valid, structured JSON."""

    def test_json_output_valid(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        args = _ns(json=True)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_contains_all_fields(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        args = _ns(json=True)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        data = json.loads(output)

        expected_keys = {
            "total_sessions",
            "with_retro",
            "without_retro",
            "rate_with_retro",
            "rate_without_retro",
            "improvement_pct",
            "estimated_savings",
            "sufficient_data",
            "top_activations",
            "dead_weight",
        }
        assert expected_keys <= set(data.keys())

    def test_json_insufficient_data_flag(self, isolated_db: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed_sessions(isolated_db, with_retro=1, without_retro=1)
        args = _ns(json=True)
        learning_db.cmd_roi(args)
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["sufficient_data"] is False
        assert data["improvement_pct"] is None


# ---------------------------------------------------------------------------
# Top activations sorted correctly
# ---------------------------------------------------------------------------


class TestTopActivations:
    """Top activations are sorted by count descending."""

    def test_sorted_by_count_desc(self, isolated_db: Path) -> None:
        _seed_activations(
            isolated_db,
            [
                ("routing", "force-route", 3),
                ("go-testing", "table-driven", 8),
                ("debugging", "stack-trace", 1),
                ("hooks", "error-learner", 5),
                ("general", "retry-pattern", 12),
                ("python", "type-hints", 2),
            ],
        )

        from learning_db_v2 import init_db

        init_db()
        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        top = data["top_activations"]
        assert len(top) == 5

        counts = [a["count"] for a in top]
        assert counts == sorted(counts, reverse=True)
        assert top[0]["count"] == 12
        assert top[0]["topic"] == "general"
        assert top[0]["key"] == "retry-pattern"

    def test_empty_activations(self, isolated_db: Path) -> None:
        from learning_db_v2 import init_db

        init_db()
        data = learning_db._compute_roi_data(isolated_db / "learning.db")
        assert data["top_activations"] == []


# ---------------------------------------------------------------------------
# Dead weight detection
# ---------------------------------------------------------------------------


class TestDeadWeight:
    """Learnings with 0 activations are detected as dead weight."""

    def test_detects_unactivated_learnings(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        _seed_learnings(isolated_db, [("hooks", "session-timing"), ("general", "placeholder-pattern")])

        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        dead_topics = {(d["topic"], d["key"]) for d in data["dead_weight"]}
        assert ("hooks", "session-timing") in dead_topics
        assert ("general", "placeholder-pattern") in dead_topics

    def test_activated_learnings_not_dead(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        _seed_learnings(isolated_db, [("routing", "force-route"), ("hooks", "unused-hook")])
        _seed_activations(isolated_db, [("routing", "force-route", 5)])

        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        dead_topics = {(d["topic"], d["key"]) for d in data["dead_weight"]}
        assert ("routing", "force-route") not in dead_topics
        assert ("hooks", "unused-hook") in dead_topics

    def test_dead_weight_includes_age(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        _seed_learnings(isolated_db, [("stale", "old-entry")])

        data = learning_db._compute_roi_data(isolated_db / "learning.db")

        dead = [d for d in data["dead_weight"] if d["topic"] == "stale"]
        assert len(dead) == 1
        assert "age_days" in dead[0]
        assert isinstance(dead[0]["age_days"], int)

    def test_no_dead_weight_when_all_activated(self, isolated_db: Path) -> None:
        _seed_sessions(isolated_db, with_retro=5, without_retro=5)
        _seed_learnings(isolated_db, [("a", "key1"), ("b", "key2")])
        _seed_activations(isolated_db, [("a", "key1", 1), ("b", "key2", 1)])

        data = learning_db._compute_roi_data(isolated_db / "learning.db")
        assert data["dead_weight"] == []

    def test_dead_weight_empty_below_10_sessions(self, isolated_db: Path) -> None:
        """ADR-032: dead weight analysis requires 10+ total sessions."""
        _seed_sessions(isolated_db, with_retro=3, without_retro=3)
        _seed_learnings(isolated_db, [("hooks", "unused-hook")])

        data = learning_db._compute_roi_data(isolated_db / "learning.db")
        assert data["dead_weight"] == []

#!/usr/bin/env python3
"""Tests for the filtered `prune` subcommand in scripts/learning-db.py.

Covers: dry-run counts, --apply deletion, graduated-row protection,
routing/effectiveness protection, filter composition, no-filter refusal,
and FTS index consistency after delete.

Run with: python3 -m pytest scripts/tests/test_learning_db_prune.py -v
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db at a temp directory for each test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    import importlib

    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    yield tmp_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def _connect(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "learning.db")
    conn.row_factory = sqlite3.Row
    return conn


def _insert(
    tmp_path: Path,
    topic: str,
    key: str,
    category: str = "error",
    confidence: float = 0.5,
    age_days: int = 0,
    graduated_to: str | None = None,
) -> None:
    """Insert a learnings row directly (FTS triggers keep the index in sync)."""
    ts = (datetime.now() - timedelta(days=age_days)).isoformat()
    conn = _connect(tmp_path)
    conn.execute(
        "INSERT INTO learnings (topic, key, value, category, confidence, source, "
        "first_seen, last_seen, graduated_to) VALUES (?, ?, ?, ?, ?, 'test', ?, ?, ?)",
        (topic, key, f"value for {topic}/{key}", category, confidence, ts, ts, graduated_to),
    )
    conn.commit()
    conn.close()


def _count(tmp_path: Path) -> int:
    conn = _connect(tmp_path)
    n = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
    conn.close()
    return n


class TestDryRun:
    def test_dry_run_is_default_and_deletes_nothing(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t1", "k1", category="error")
        _insert(isolated_db, "t2", "k2", category="design")

        result = _run_cli("prune", "--category", "error")
        assert result.returncode == 0
        assert "Matched for prune: 1" in result.stdout
        assert "DRY RUN" in result.stdout
        assert "Back up" in result.stdout
        assert _count(isolated_db) == 2

    def test_dry_run_counts_per_filter_combo(self, isolated_db: Path) -> None:
        _insert(isolated_db, "unknown", "k1", category="error", confidence=0.3)
        _insert(isolated_db, "unknown", "k2", category="error", confidence=0.9)
        _insert(isolated_db, "real-topic", "k3", category="error", confidence=0.3)

        result = _run_cli("prune", "--category", "error", "--topic", "unknown", "--max-confidence", "0.5")
        assert result.returncode == 0
        assert "Matched for prune: 1" in result.stdout
        assert "[error] unknown" in result.stdout

    def test_older_than_filter(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "old", category="error", age_days=100)
        _insert(isolated_db, "t", "new", category="error", age_days=1)

        result = _run_cli("prune", "--category", "error", "--older-than", "30")
        assert result.returncode == 0
        assert "Matched for prune: 1" in result.stdout

    def test_no_filter_refused(self, isolated_db: Path) -> None:
        result = _run_cli("prune")
        assert result.returncode == 2
        assert "at least one filter" in result.stderr

    def test_total_before_printed(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "k", category="error")
        result = _run_cli("prune", "--category", "error", "--dry-run")
        assert result.returncode == 0
        assert "Total learnings before: 1" in result.stdout


class TestApply:
    def test_apply_deletes_matched_rows(self, isolated_db: Path) -> None:
        _insert(isolated_db, "unknown", "k1", category="error")
        _insert(isolated_db, "keep", "k2", category="design")

        result = _run_cli("prune", "--category", "error", "--apply")
        assert result.returncode == 0
        assert "Deleted 1 entries" in result.stdout
        assert "1 -> " not in result.stdout.split("Deleted")[0]  # before/after on the delete line
        assert "2 -> 1" in result.stdout
        assert _count(isolated_db) == 1

    def test_apply_protects_graduated_rows(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "grad", category="error", graduated_to="agent:x")
        _insert(isolated_db, "t", "plain", category="error")

        result = _run_cli("prune", "--category", "error", "--apply")
        assert result.returncode == 0
        assert "Deleted 1 entries" in result.stdout

        conn = _connect(isolated_db)
        rows = conn.execute("SELECT key FROM learnings").fetchall()
        conn.close()
        assert [r["key"] for r in rows] == ["grad"]

    def test_apply_protects_routing_effectiveness_rows(self, isolated_db: Path) -> None:
        """Rows read by route-weights/route-health are never pruned."""
        _insert(isolated_db, "routing", "agent:skill", category="effectiveness", confidence=0.1)
        _insert(isolated_db, "t", "plain", category="effectiveness", confidence=0.1)

        result = _run_cli("prune", "--category", "effectiveness", "--max-confidence", "0.5", "--apply")
        assert result.returncode == 0
        assert "Deleted 1 entries" in result.stdout

        conn = _connect(isolated_db)
        rows = conn.execute("SELECT topic FROM learnings").fetchall()
        conn.close()
        assert [r["topic"] for r in rows] == ["routing"]

    def test_dry_run_and_apply_mutually_exclusive(self, isolated_db: Path) -> None:
        result = _run_cli("prune", "--category", "error", "--dry-run", "--apply")
        assert result.returncode != 0


class TestFTSConsistency:
    def test_fts_index_consistent_after_apply(self, isolated_db: Path) -> None:
        _insert(isolated_db, "deleteme", "k1", category="error")
        _insert(isolated_db, "keepme", "k2", category="design")

        result = _run_cli("prune", "--category", "error", "--apply")
        assert result.returncode == 0

        conn = _connect(isolated_db)
        # FTS integrity check raises SQLITE_CORRUPT_VTAB on a desynced index.
        conn.execute("INSERT INTO learnings_fts(learnings_fts, rank) VALUES('integrity-check', 0)")
        gone = conn.execute("SELECT COUNT(*) FROM learnings_fts WHERE learnings_fts MATCH 'deleteme'").fetchone()[0]
        kept = conn.execute("SELECT COUNT(*) FROM learnings_fts WHERE learnings_fts MATCH 'keepme'").fetchone()[0]
        conn.close()
        assert gone == 0
        assert kept == 1

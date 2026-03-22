#!/usr/bin/env python3
"""Tests for the stale detection and pruning subcommands in learning-db.py.

Run with: python3 -m pytest hooks/tests/test_stale_pruner.py -v
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add hooks/lib to path for learning_db_v2
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

from learning_db_v2 import get_db_path, init_db, record_learning

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db to a temp directory for each test."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    # Force-reload the module to pick up new env and clear all cached state.
    # Other test files (e.g. test_learning_roi.py) manipulate sys.path and
    # reload learning_db_v2 from different locations, which can leave the
    # module pointing at a stale DB path when running in the full test suite.
    import importlib

    import learning_db_v2

    importlib.reload(learning_db_v2)
    # Re-import after reload to get fresh references
    from learning_db_v2 import init_db as fresh_init

    fresh_init()
    yield tmp_path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run learning-db.py with given args, returning completed process."""
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def _insert_old_entry(
    topic: str,
    key: str,
    value: str = "test value",
    confidence: float = 0.3,
    age_days: int = 60,
    graduated_to: str | None = None,
) -> None:
    """Insert an entry with a backdated first_seen timestamp."""
    record_learning(topic=topic, key=key, value=value, category="design", confidence=confidence)

    old_date = (datetime.now() - timedelta(days=age_days)).isoformat()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE learnings SET first_seen = ?, last_seen = ? WHERE topic = ? AND key = ?",
        (old_date, old_date, topic, key),
    )
    if graduated_to:
        conn.execute(
            "UPDATE learnings SET graduated_to = ? WHERE topic = ? AND key = ?",
            (graduated_to, topic, key),
        )
    # Override confidence directly (record_learning may use category default)
    conn.execute(
        "UPDATE learnings SET confidence = ? WHERE topic = ? AND key = ?",
        (confidence, topic, key),
    )
    conn.commit()
    conn.close()


# ── stale subcommand tests ───────────────────────────────────────


class TestStaleSubcommand:
    """Tests for the `stale` subcommand."""

    def test_stale_no_entries(self) -> None:
        result = _run_cli("stale")
        assert result.returncode == 0
        assert "No stale entries found" in result.stdout

    def test_stale_finds_old_low_confidence_entries(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-23ae96e7", confidence=0.4, age_days=45)

        result = _run_cli("stale")
        assert result.returncode == 0
        assert "2 found" in result.stdout
        assert "test-a2f7b882" in result.stdout
        assert "test-23ae96e7" in result.stdout

    def test_stale_excludes_high_confidence(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "high-conf", confidence=0.8, age_days=60)

        result = _run_cli("stale")
        assert result.returncode == 0
        assert "test-a2f7b882" in result.stdout
        assert "high-conf" not in result.stdout

    def test_stale_excludes_graduated(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-5bcf34ca", confidence=0.2, age_days=60, graduated_to="agent:test")

        result = _run_cli("stale")
        assert result.returncode == 0
        assert "test-a2f7b882" in result.stdout
        assert "test-5bcf34ca" not in result.stdout

    def test_stale_excludes_recent_entries(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "recent-entry", confidence=0.3, age_days=5)

        result = _run_cli("stale")
        assert result.returncode == 0
        assert "test-a2f7b882" in result.stdout
        assert "recent-entry" not in result.stdout

    def test_stale_custom_min_age(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-23ae96e7", confidence=0.3, age_days=45)

        result = _run_cli("stale", "--min-age-days", "50")
        assert result.returncode == 0
        assert "test-a2f7b882" in result.stdout
        assert "test-23ae96e7" not in result.stdout

    def test_stale_json_output(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)

        result = _run_cli("stale", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["topic"] == "test-topic"
        assert data[0]["key"] == "test-a2f7b882"
        assert data[0]["confidence"] == 0.3

    def test_stale_sorted_by_confidence_ascending(self) -> None:
        _insert_old_entry("test-topic", "low-conf", confidence=0.1, age_days=60)
        _insert_old_entry("test-topic", "mid-conf", confidence=0.4, age_days=60)
        _insert_old_entry("test-topic", "lower-conf", confidence=0.2, age_days=60)

        result = _run_cli("stale", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        confidences = [entry["confidence"] for entry in data]
        assert confidences == sorted(confidences)


# ── stale-prune subcommand tests ─────────────────────────────────


class TestStalePruneSubcommand:
    """Tests for the `stale-prune` subcommand."""

    def test_stale_prune_requires_flag(self) -> None:
        result = _run_cli("stale-prune")
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_stale_prune_dry_run_no_entries(self) -> None:
        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout

    def test_stale_prune_dry_run_shows_candidates(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-23ae96e7", confidence=0.4, age_days=45)

        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert "Would archive 2 stale entries" in result.stdout
        assert "test-a2f7b882" in result.stdout
        assert "test-23ae96e7" in result.stdout

        # Verify nothing was actually deleted
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        conn.close()
        assert count == 2

    def test_stale_prune_confirm_archives_entries(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-23ae96e7", confidence=0.4, age_days=45)
        # This one should NOT be archived (high confidence)
        _insert_old_entry("test-topic", "keeper", confidence=0.8, age_days=60)

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "Archived 2 stale entries" in result.stdout

        # Verify entries moved to archive
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)

        # learnings table should have only the keeper
        remaining = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        assert remaining == 1

        kept = conn.execute("SELECT key FROM learnings").fetchone()[0]
        assert kept == "keeper"

        # archive table should have the 2 stale entries
        archived = conn.execute("SELECT COUNT(*) FROM learning_archive").fetchone()[0]
        assert archived == 2

        # Verify archive has correct columns
        row = conn.execute("SELECT * FROM learning_archive WHERE key = ?", ("test-a2f7b882",)).fetchone()
        assert row is not None

        conn.close()

    def test_stale_prune_archive_table_schema(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        row = conn.execute("SELECT * FROM learning_archive").fetchone()
        columns = row.keys()
        assert "id" in columns
        assert "topic" in columns
        assert "key" in columns
        assert "value" in columns
        assert "confidence" in columns
        assert "category" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
        assert "archived_at" in columns

        # archived_at should be populated
        assert row["archived_at"] is not None
        # created_at maps from first_seen
        assert row["created_at"] is not None
        conn.close()

    def test_stale_prune_confirm_no_stale(self) -> None:
        _insert_old_entry("test-topic", "keeper", confidence=0.8, age_days=60)

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout

    def test_stale_prune_custom_min_age(self) -> None:
        _insert_old_entry("test-topic", "test-a2f7b882", confidence=0.3, age_days=60)
        _insert_old_entry("test-topic", "test-23ae96e7", confidence=0.3, age_days=45)

        result = _run_cli("stale-prune", "--confirm", "--min-age-days", "50")
        assert result.returncode == 0
        assert "Archived 1 stale entries" in result.stdout

        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        remaining = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        assert remaining == 1
        conn.close()

    def test_stale_prune_does_not_archive_graduated(self) -> None:
        _insert_old_entry("test-topic", "test-5bcf34ca", confidence=0.2, age_days=60, graduated_to="agent:test")

        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout

    def test_stale_prune_mutually_exclusive_flags(self) -> None:
        result = _run_cli("stale-prune", "--dry-run", "--confirm")
        assert result.returncode != 0


# ── existing subcommand regression tests ─────────────────────────


class TestExistingSubcommands:
    """Verify existing subcommands still work after changes."""

    def test_legacy_prune_still_works(self) -> None:
        result = _run_cli("prune", "--below-confidence", "0.3", "--older-than", "90")
        assert result.returncode == 0
        assert "Pruned" in result.stdout

    def test_stats_still_works(self) -> None:
        result = _run_cli("stats")
        assert result.returncode == 0
        assert "Total learnings" in result.stdout

    def test_record_still_works(self) -> None:
        result = _run_cli("record", "test-topic", "test-key", "test value", "--category", "design")
        assert result.returncode == 0
        assert "Recorded" in result.stdout

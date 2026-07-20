#!/usr/bin/env python3
"""Tests for the `stale` / `stale-prune` subcommands in scripts/learning-db.py.

`retro clear` (skills/meta/retro/SKILL.md) wraps these two commands, so this
file is also the test coverage for that subcommand's dry-run gate
(ADR: pretool-injector-scoping, acceptance criterion "retro clear dry-run
gate"). Covers: dry-run-by-default behavior, --confirm archiving, the
required mutually-exclusive flag gate, and the underlying staleness filter
(age, confidence, graduation).

Run with: python3 -m pytest scripts/tests/test_learning_db_stale_prune.py -v
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
    confidence: float = 0.3,
    age_days: int = 60,
    graduated_to: str | None = None,
) -> None:
    """Insert a learnings row directly with a controlled age/confidence."""
    ts = (datetime.now() - timedelta(days=age_days)).isoformat()
    conn = _connect(tmp_path)
    conn.execute(
        "INSERT INTO learnings (topic, key, value, category, confidence, source, "
        "first_seen, last_seen, graduated_to) VALUES (?, ?, ?, 'error', ?, 'test', ?, ?, ?)",
        (topic, key, f"value for {topic}/{key}", confidence, ts, ts, graduated_to),
    )
    conn.commit()
    conn.close()


def _count(tmp_path: Path) -> int:
    conn = _connect(tmp_path)
    n = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
    conn.close()
    return n


class TestRequiredFlag:
    def test_neither_dry_run_nor_confirm_is_rejected(self, isolated_db: Path) -> None:
        """The mutually-exclusive group is `required=True` -- silent deletion
        by omission is impossible; the CLI refuses to run at all."""
        result = _run_cli("stale-prune")
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "one of the arguments" in result.stderr.lower()

    def test_both_flags_together_is_rejected(self, isolated_db: Path) -> None:
        result = _run_cli("stale-prune", "--dry-run", "--confirm")
        assert result.returncode != 0


class TestDryRun:
    def test_dry_run_deletes_nothing(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t1", "k1", confidence=0.2, age_days=60)

        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert "Run with --confirm" in result.stdout
        assert _count(isolated_db) == 1

    def test_dry_run_lists_matching_entries(self, isolated_db: Path) -> None:
        _insert(isolated_db, "stale-topic", "stale-key", confidence=0.2, age_days=60)
        _insert(isolated_db, "fresh-topic", "fresh-key", confidence=0.9, age_days=1)

        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "stale-topic/stale-key" in result.stdout
        assert "fresh-topic/fresh-key" not in result.stdout

    def test_dry_run_respects_min_age_days(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "young", confidence=0.2, age_days=10)

        result = _run_cli("stale-prune", "--dry-run", "--min-age-days", "30")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout
        assert _count(isolated_db) == 1

    def test_dry_run_no_stale_entries_message(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "k", confidence=0.95, age_days=1)

        result = _run_cli("stale-prune", "--dry-run")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout


class TestConfirm:
    def test_confirm_archives_and_deletes(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t1", "k1", confidence=0.2, age_days=60)
        _insert(isolated_db, "t2", "k2", confidence=0.9, age_days=1)  # not stale

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "Archived 1 stale entries" in result.stdout
        assert _count(isolated_db) == 1  # only the fresh row remains

        conn = _connect(isolated_db)
        archived = conn.execute("SELECT topic, key FROM learning_archive").fetchall()
        conn.close()
        assert [(r["topic"], r["key"]) for r in archived] == [("t1", "k1")]

    def test_confirm_protects_graduated_rows(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "grad", confidence=0.1, age_days=90, graduated_to="agent:x")

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout
        assert _count(isolated_db) == 1

    def test_confirm_protects_high_confidence_rows(self, isolated_db: Path) -> None:
        """Staleness requires confidence < 0.5 -- a high-confidence old row is untouched."""
        _insert(isolated_db, "t", "old-but-trusted", confidence=0.85, age_days=200)

        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout
        assert _count(isolated_db) == 1

    def test_confirm_with_no_stale_entries_reports_and_exits_clean(self, isolated_db: Path) -> None:
        result = _run_cli("stale-prune", "--confirm")
        assert result.returncode == 0
        assert "No stale entries to archive" in result.stdout


class TestStaleShow:
    def test_stale_lists_without_deleting(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "k", confidence=0.2, age_days=60)

        result = _run_cli("stale")
        assert result.returncode == 0
        assert "t" in result.stdout
        assert _count(isolated_db) == 1

    def test_stale_json_output(self, isolated_db: Path) -> None:
        _insert(isolated_db, "t", "k", confidence=0.2, age_days=60)

        result = _run_cli("stale", "--json")
        assert result.returncode == 0
        import json

        entries = json.loads(result.stdout)
        assert len(entries) == 1
        assert entries[0]["topic"] == "t"

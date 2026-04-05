"""Tests for scripts/retro-impact-analysis.py.

Covers DB querying, markdown output, JSON output, significance testing,
and graceful handling of missing DB / table.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module and script path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "retro-impact-analysis.py"


def _load_module():
    """Load retro-impact-analysis.py as a Python module.

    Returns:
        Loaded module object.
    """
    spec = importlib.util.spec_from_file_location("retro_impact_analysis", str(_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _create_db(path: Path) -> None:
    """Create session_stats table in SQLite DB at path.

    Args:
        path: Filesystem path for the new database file.
    """
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE session_stats (
            session_id TEXT PRIMARY KEY,
            had_retro_knowledge INTEGER NOT NULL,
            errors_encountered INTEGER NOT NULL DEFAULT 0,
            errors_resolved INTEGER NOT NULL DEFAULT 0,
            timestamp TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_sessions(
    path: Path,
    had_retro: int,
    count: int,
    errors_encountered: int = 1,
    errors_resolved: int = 1,
    prefix: str = "s",
) -> None:
    """Insert N session rows with uniform error counts.

    Args:
        path: Path to SQLite database.
        had_retro: Value for had_retro_knowledge column (0 or 1).
        count: Number of rows to insert.
        errors_encountered: Errors encountered per session.
        errors_resolved: Errors resolved per session.
        prefix: Prefix for generated session IDs to avoid collisions.
    """
    conn = sqlite3.connect(str(path))
    rows = [
        (f"{prefix}-retro{had_retro}-{i}", had_retro, errors_encountered, errors_resolved, "2026-04-04")
        for i in range(count)
    ]
    conn.executemany(
        "INSERT INTO session_stats VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _run_script(db_path: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run retro-impact-analysis.py as a subprocess.

    Args:
        db_path: Path to the test database.
        extra_args: Additional CLI arguments.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    cmd = [sys.executable, str(_SCRIPT), "--db", str(db_path)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=15)


# ---------------------------------------------------------------------------
# Tests: DB not found
# ---------------------------------------------------------------------------


class TestMissingDatabase:
    """Graceful handling when DB file does not exist."""

    def test_missing_db_exits_nonzero(self, tmp_path: Path):
        """Script exits with code 1 when DB file is missing.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        result = _run_script(tmp_path / "nonexistent.db")
        assert result.returncode == 1

    def test_missing_db_error_message(self, tmp_path: Path):
        """Script prints 'not found' to stderr when DB file is missing.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        result = _run_script(tmp_path / "nonexistent.db")
        assert "not found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Tests: Table not found
# ---------------------------------------------------------------------------


class TestMissingTable:
    """Graceful handling when session_stats table does not exist."""

    def test_missing_table_exits_nonzero(self, tmp_path: Path):
        """Script exits with code 1 when session_stats table is absent.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.commit()
        conn.close()

        result = _run_script(db)
        assert result.returncode == 1

    def test_missing_table_error_message(self, tmp_path: Path):
        """Script mentions session_stats in stderr when table is absent.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE unrelated (id INTEGER)")
        conn.commit()
        conn.close()

        result = _run_script(db)
        assert "session_stats" in result.stderr


# ---------------------------------------------------------------------------
# Tests: Insufficient data
# ---------------------------------------------------------------------------


class TestInsufficientData:
    """Verdict when session count is below --min-sessions threshold."""

    def test_few_sessions_verdict_insufficient(self, tmp_path: Path):
        """Fewer than 20 sessions per cohort → INSUFFICIENT DATA verdict.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=5, prefix="r")
        _insert_sessions(db, had_retro=0, count=5, prefix="c")

        result = _run_script(db)
        assert result.returncode == 0
        assert "INSUFFICIENT DATA" in result.stdout

    def test_custom_min_sessions_threshold(self, tmp_path: Path):
        """10 sessions per cohort passes when --min-sessions 5.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=10, prefix="r")
        _insert_sessions(db, had_retro=0, count=10, prefix="c")

        result = _run_script(db, ["--min-sessions", "5"])
        assert result.returncode == 0
        assert "INSUFFICIENT DATA" not in result.stdout

    def test_one_cohort_missing_is_insufficient(self, tmp_path: Path):
        """Only retro cohort populated → INSUFFICIENT DATA.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=30, prefix="r")

        result = _run_script(db)
        assert result.returncode == 0
        assert "INSUFFICIENT DATA" in result.stdout


# ---------------------------------------------------------------------------
# Tests: Significant result
# ---------------------------------------------------------------------------


class TestSignificantResult:
    """Verdict when cohorts are large and error rates diverge clearly."""

    def test_large_clear_difference_is_significant(self, tmp_path: Path):
        """100 sessions each with very different error rates → SIGNIFICANT.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        # Retro sessions: 0 errors each
        _insert_sessions(db, had_retro=1, count=100, errors_encountered=0, prefix="r")
        # Control sessions: 1 error each
        _insert_sessions(db, had_retro=0, count=100, errors_encountered=1, prefix="c")

        result = _run_script(db, ["--min-sessions", "20"])
        assert result.returncode == 0
        assert "SIGNIFICANT" in result.stdout

    def test_session_counts_in_output(self, tmp_path: Path):
        """Output markdown table shows the correct session counts.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=30, prefix="r")
        _insert_sessions(db, had_retro=0, count=25, prefix="c")

        result = _run_script(db)
        assert result.returncode == 0
        assert "30" in result.stdout
        assert "25" in result.stdout


# ---------------------------------------------------------------------------
# Tests: Not significant result
# ---------------------------------------------------------------------------


class TestNotSignificantResult:
    """Verdict when cohorts are large but error rates are identical."""

    def test_identical_rates_not_significant(self, tmp_path: Path):
        """Identical error rates across large cohorts → NOT SIGNIFICANT.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=50, errors_encountered=1, prefix="r")
        _insert_sessions(db, had_retro=0, count=50, errors_encountered=1, prefix="c")

        result = _run_script(db, ["--min-sessions", "20"])
        assert result.returncode == 0
        assert "NOT SIGNIFICANT" in result.stdout


# ---------------------------------------------------------------------------
# Tests: JSON output
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """--json flag produces valid JSON with expected structure."""

    def test_json_output_is_valid(self, tmp_path: Path):
        """--json produces parseable JSON.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=10, prefix="r")
        _insert_sessions(db, had_retro=0, count=10, prefix="c")

        result = _run_script(db, ["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_json_has_required_keys(self, tmp_path: Path):
        """JSON output contains verdict, retro, control keys.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=5, prefix="r")
        _insert_sessions(db, had_retro=0, count=5, prefix="c")

        result = _run_script(db, ["--json"])
        data = json.loads(result.stdout)
        assert "verdict" in data
        assert "retro" in data
        assert "control" in data

    def test_json_session_counts_match(self, tmp_path: Path):
        """JSON retro.sessions and control.sessions match inserted data.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=7, prefix="r")
        _insert_sessions(db, had_retro=0, count=13, prefix="c")

        result = _run_script(db, ["--json"])
        data = json.loads(result.stdout)
        assert data["retro"]["sessions"] == 7
        assert data["control"]["sessions"] == 13

    def test_json_insufficient_data_has_null_diff(self, tmp_path: Path):
        """Insufficient data → JSON diff and CI fields are null.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=2, prefix="r")
        _insert_sessions(db, had_retro=0, count=2, prefix="c")

        result = _run_script(db, ["--json"])
        data = json.loads(result.stdout)
        assert data["diff"] is None
        assert data["ci_95_lower"] is None
        assert data["ci_95_upper"] is None


# ---------------------------------------------------------------------------
# Tests: Markdown output structure
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    """Verify markdown table structure in default output."""

    def test_markdown_contains_table_header(self, tmp_path: Path):
        """Markdown output contains | Cohort | header row.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=5, prefix="r")
        _insert_sessions(db, had_retro=0, count=5, prefix="c")

        result = _run_script(db)
        assert "| Cohort |" in result.stdout

    def test_markdown_contains_verdict_line(self, tmp_path: Path):
        """Markdown output ends with **Verdict: ...** line.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        db = tmp_path / "learning.db"
        _create_db(db)
        _insert_sessions(db, had_retro=1, count=5, prefix="r")
        _insert_sessions(db, had_retro=0, count=5, prefix="c")

        result = _run_script(db)
        assert "**Verdict:" in result.stdout


# ---------------------------------------------------------------------------
# Unit tests: internal functions
# ---------------------------------------------------------------------------


class TestInternalFunctions:
    """Unit tests for _compute_ci and _build_report."""

    def test_compute_ci_symmetric(self):
        """95% CI with equal proportions and sizes is centred on 0.

        Diff should be 0.0 with symmetric bounds.
        """
        diff, lower, upper = _mod._compute_ci(0.5, 100, 0.5, 100)
        assert abs(diff) < 1e-10
        assert lower < 0 < upper

    def test_compute_ci_excludes_zero_when_large_gap(self):
        """Large proportion gap with big N should exclude 0 from CI.

        p1=0.9, p2=0.1 with n=1000 each should be clearly significant.
        """
        diff, lower, upper = _mod._compute_ci(0.9, 1000, 0.1, 1000)
        assert lower > 0, "CI should exclude 0 for large effect with large N"

    def test_build_report_insufficient_when_below_min(self):
        """_build_report returns INSUFFICIENT DATA when below min_sessions.

        Args: none (uses inline cohort data).
        """
        cohorts = {
            1: {"session_count": 5, "avg_errors_encountered": 0.5, "avg_errors_resolved": 0.5},
            0: {"session_count": 5, "avg_errors_encountered": 0.5, "avg_errors_resolved": 0.5},
        }
        report = _mod._build_report(cohorts, min_sessions=20)
        assert report["verdict"] == "INSUFFICIENT DATA"
        assert report["diff"] is None

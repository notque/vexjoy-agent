"""Tests for the learning-db.py ``record-invalid-route`` subcommand.

Covers:
- A new invalid-route record is inserted with the correct topic/key/category.
- Repeated calls with the same kind+name increment observation_count.
- Different names produce distinct rows.
- Missing --kind or --name fails argparse validation.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo hooks/lib is on the path for learning_db_v2.
_repo_root = Path(__file__).resolve().parent.parent.parent
_repo_hooks_lib = str(_repo_root / "hooks" / "lib")
if _repo_hooks_lib not in sys.path:
    sys.path.insert(0, _repo_hooks_lib)

_SCRIPT_PATH = _repo_root / "scripts" / "learning-db.py"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the learning DB at a temp directory so tests never touch production data."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))

    import learning_db_v2

    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    if "learning_db_v2" in sys.modules:
        importlib.reload(sys.modules["learning_db_v2"])
    return db_dir


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Invoke the learning-db.py CLI as a subprocess with CLAUDE_LEARNING_DIR honored."""
    import os

    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_record_invalid_route_creates_row(isolated_db: Path) -> None:
    """The first call inserts a fresh invalid-route row."""
    result = _run_cli("record-invalid-route", "--kind", "agent", "--name", "benchmark")
    assert result.returncode == 0, result.stderr
    assert "Recorded: [invalid-route]" in result.stdout

    # Verify the row landed in the DB with the expected shape.
    import learning_db_v2

    rows = learning_db_v2.query_learnings(topic="invalid-route")
    assert len(rows) == 1
    row = rows[0]
    assert row["topic"] == "invalid-route"
    assert row["key"] == "agent:benchmark"
    assert row["category"] == "effectiveness"
    assert "router picked invalid agent: benchmark" in row["value"]
    assert row["observation_count"] == 1


def test_record_invalid_route_increments_observation_count(isolated_db: Path) -> None:
    """Calling twice with the same kind+name updates the existing row."""
    r1 = _run_cli("record-invalid-route", "--kind", "agent", "--name", "benchmark")
    assert r1.returncode == 0, r1.stderr
    r2 = _run_cli("record-invalid-route", "--kind", "agent", "--name", "benchmark")
    assert r2.returncode == 0, r2.stderr

    import learning_db_v2

    rows = learning_db_v2.query_learnings(topic="invalid-route")
    assert len(rows) == 1
    assert rows[0]["observation_count"] == 2


def test_record_invalid_route_distinguishes_kind_and_name(isolated_db: Path) -> None:
    """Different kinds or names create distinct rows."""
    _run_cli("record-invalid-route", "--kind", "agent", "--name", "benchmark")
    _run_cli("record-invalid-route", "--kind", "skill", "--name", "benchmark")
    _run_cli("record-invalid-route", "--kind", "agent", "--name", "fake-other")

    import learning_db_v2

    rows = learning_db_v2.query_learnings(topic="invalid-route", limit=10)
    keys = {r["key"] for r in rows}
    assert keys == {"agent:benchmark", "skill:benchmark", "agent:fake-other"}


def test_record_invalid_route_with_reason(isolated_db: Path) -> None:
    """The --reason flag appends context to the stored value."""
    result = _run_cli(
        "record-invalid-route",
        "--kind",
        "agent",
        "--name",
        "benchmark",
        "--reason",
        "closest matches: code-reviewer, python-general-engineer",
    )
    assert result.returncode == 0, result.stderr

    import learning_db_v2

    rows = learning_db_v2.query_learnings(topic="invalid-route")
    assert len(rows) == 1
    assert "closest matches: code-reviewer" in rows[0]["value"]


def test_record_invalid_route_rejects_missing_kind(isolated_db: Path) -> None:
    """Argparse rejects invocation without --kind."""
    result = _run_cli("record-invalid-route", "--name", "benchmark")
    assert result.returncode != 0
    assert "required" in result.stderr.lower() or "--kind" in result.stderr


def test_record_invalid_route_rejects_invalid_kind(isolated_db: Path) -> None:
    """Argparse rejects kinds outside {agent, skill}."""
    result = _run_cli("record-invalid-route", "--kind", "other", "--name", "benchmark")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower()

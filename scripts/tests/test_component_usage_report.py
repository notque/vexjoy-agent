"""Tests for component-usage-report.py (ADR-174).

Covers:
- Full component list from INDEX files appears in output
- Ranking is correct (highest count first)
- --dead-only filters to zero-count components
- --top N limits output
- --json produces valid JSON
- Missing database prints error message and exits 1
"""

from __future__ import annotations

import importlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))
cur = importlib.import_module("component-usage-report")
sys.path.pop(0)

SCRIPT_PATH = _SCRIPTS_DIR / "component-usage-report.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def usage_db(tmp_path: Path) -> Path:
    """Create a temp SQLite database with known skill and agent invocation data."""
    db_path = tmp_path / "usage.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE skill_invocations (skill_name TEXT, timestamp TEXT)")
    conn.execute("CREATE TABLE agent_invocations (agent_name TEXT, timestamp TEXT)")

    # Insert known data: skill-alpha=5, skill-beta=2, skill-gamma=0 (not inserted)
    conn.executemany(
        "INSERT INTO skill_invocations VALUES (?, ?)",
        [
            ("skill-alpha", "2026-01-01T10:00:00"),
            ("skill-alpha", "2026-01-02T10:00:00"),
            ("skill-alpha", "2026-01-03T10:00:00"),
            ("skill-alpha", "2026-01-04T10:00:00"),
            ("skill-alpha", "2026-01-05T10:00:00"),
            ("skill-beta", "2026-01-01T10:00:00"),
            ("skill-beta", "2026-01-02T10:00:00"),
        ],
    )

    # agent-one=3, agent-two=1
    conn.executemany(
        "INSERT INTO agent_invocations VALUES (?, ?)",
        [
            ("agent-one", "2026-01-01T10:00:00"),
            ("agent-one", "2026-01-02T10:00:00"),
            ("agent-one", "2026-01-03T10:00:00"),
            ("agent-two", "2026-01-01T10:00:00"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def index_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temp INDEX.json files and patch REPO_ROOT in the module."""
    agents_dir = tmp_path / "agents"
    skills_dir = tmp_path / "skills"
    agents_dir.mkdir()
    skills_dir.mkdir()

    agents_index = {
        "version": "1",
        "agents": {
            "agent-one": {"description": "Agent one"},
            "agent-two": {"description": "Agent two"},
            "agent-three": {"description": "Agent three (dead)"},
        },
    }
    skills_index = {
        "version": "1",
        "skills": {
            "skill-alpha": {"description": "Skill alpha"},
            "skill-beta": {"description": "Skill beta"},
            "skill-gamma": {"description": "Skill gamma (dead)"},
        },
    }

    (agents_dir / "INDEX.json").write_text(json.dumps(agents_index), encoding="utf-8")
    (skills_dir / "INDEX.json").write_text(json.dumps(skills_index), encoding="utf-8")

    monkeypatch.setattr(cur, "REPO_ROOT", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests (module-level functions)
# ---------------------------------------------------------------------------


def test_load_index_components_agents(index_files: Path) -> None:
    """load_index_components returns agent names from INDEX.json."""
    agents = cur.load_index_components(index_files / "agents" / "INDEX.json", "agents")
    assert sorted(agents) == ["agent-one", "agent-three", "agent-two"]


def test_load_index_components_missing_file(tmp_path: Path) -> None:
    """load_index_components returns empty list when file doesn't exist."""
    result = cur.load_index_components(tmp_path / "nonexistent" / "INDEX.json", "agents")
    assert result == []


def test_query_usage_counts(usage_db: Path) -> None:
    """query_usage returns correct counts and last timestamps."""
    skill_counts, skill_last, agent_counts, agent_last = cur.query_usage(usage_db)
    assert skill_counts["skill-alpha"] == 5
    assert skill_counts["skill-beta"] == 2
    assert agent_counts["agent-one"] == 3
    assert agent_counts["agent-two"] == 1
    assert "skill-gamma" not in skill_counts
    assert skill_last["skill-alpha"] == "2026-01-05T10:00:00"


def test_query_usage_missing_tables(tmp_path: Path) -> None:
    """query_usage returns empty dicts when tables don't exist."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    conn.close()
    skill_counts, skill_last, agent_counts, agent_last = cur.query_usage(db_path)
    assert skill_counts == {}
    assert agent_counts == {}


def test_build_report_ranking(usage_db: Path, index_files: Path) -> None:
    """build_report returns rows sorted by invocation_count descending."""
    rows = cur.build_report(usage_db, top_n=None, dead_only=False)
    counts = [r["invocation_count"] for r in rows]
    assert counts == sorted(counts, reverse=True)


def test_build_report_includes_dead_components(usage_db: Path, index_files: Path) -> None:
    """build_report includes components with 0 invocations."""
    rows = cur.build_report(usage_db, top_n=None, dead_only=False)
    names = [r["name"] for r in rows]
    assert "skill-gamma" in names
    assert "agent-three" in names


def test_build_report_dead_only(usage_db: Path, index_files: Path) -> None:
    """build_report with dead_only=True returns only 0-count components."""
    rows = cur.build_report(usage_db, top_n=None, dead_only=True)
    assert all(r["invocation_count"] == 0 for r in rows)
    names = [r["name"] for r in rows]
    assert "skill-gamma" in names
    assert "agent-three" in names
    assert "skill-alpha" not in names


def test_build_report_top_n(usage_db: Path, index_files: Path) -> None:
    """build_report with top_n=2 returns exactly 2 rows."""
    rows = cur.build_report(usage_db, top_n=2, dead_only=False)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Subprocess (CLI) tests
# ---------------------------------------------------------------------------


def _run(args: list[str]) -> subprocess.CompletedProcess:
    """Run the script via subprocess and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
    )


def test_cli_markdown_output(usage_db: Path) -> None:
    """CLI default output is a markdown table with correct structure.

    The subprocess reads the real repo INDEX files, so we check for
    structural correctness and known real-index entries rather than
    test-fixture component names (monkeypatch doesn't cross subprocess
    boundaries).
    """
    result = _run(["--usage-db", str(usage_db)])
    assert result.returncode == 0
    # Markdown table header row
    assert "| # |" in result.stdout
    assert "| Name |" in result.stdout
    assert "| Invocations |" in result.stdout
    # Separator row
    assert "|---|" in result.stdout
    # Real INDEX entries (present in every build of the repo)
    assert "adr-consultation" in result.stdout
    assert "ansible-automation-engineer" in result.stdout


def test_cli_json_output(usage_db: Path) -> None:
    """--json flag produces valid JSON list."""
    result = _run(["--usage-db", str(usage_db), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    # Must have invocation_count key
    assert all("invocation_count" in r for r in data)


def test_cli_top_n(usage_db: Path) -> None:
    """--top 2 limits JSON output to 2 rows."""
    result = _run(["--usage-db", str(usage_db), "--json", "--top", "2"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2


def test_cli_dead_only(usage_db: Path) -> None:
    """--dead-only returns only zero-count components in JSON output."""
    result = _run(["--usage-db", str(usage_db), "--json", "--dead-only"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert all(r["invocation_count"] == 0 for r in data)


def test_cli_ranking_order(usage_db: Path) -> None:
    """JSON output is ranked highest-count first."""
    result = _run(["--usage-db", str(usage_db), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    counts = [r["invocation_count"] for r in data]
    assert counts == sorted(counts, reverse=True)


def test_cli_missing_db(tmp_path: Path) -> None:
    """Missing usage.db prints error message and exits 1."""
    missing = tmp_path / "nonexistent.db"
    result = _run(["--usage-db", str(missing)])
    assert result.returncode == 1
    assert "error" in result.stderr.lower()
    assert str(missing) in result.stderr


def test_cli_json_schema(usage_db: Path) -> None:
    """JSON output contains required fields for each record."""
    result = _run(["--usage-db", str(usage_db), "--json"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    required_keys = {"name", "component_type", "invocation_count", "last_used"}
    for record in data:
        assert required_keys.issubset(record.keys()), f"Missing keys in: {record}"

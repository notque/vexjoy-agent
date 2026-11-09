"""Tests for `learning-db.py route-stats --by agent|skill|force-route|errors|override`.

Covers: bookkeeping rows (stack-usage, fallback-reason) are not counted as
routes, and --json prints one parseable JSON report and nothing else.

Run with: python3 -m pytest scripts/tests/test_learning_db_route_stats.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root / "hooks" / "lib"))

SCRIPT_PATH = str(_repo_root / "scripts" / "learning-db.py")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point learning.db at a temp directory and seed route and bookkeeping rows."""
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))

    import learning_db_v2

    # No reload: it rebinds module globals for later tests in the same worker.
    monkeypatch.setattr(learning_db_v2, "_initialized", False)
    learning_db_v2.init_db()
    yield tmp_path


def _record(key: str, value: str) -> None:
    import learning_db_v2

    learning_db_v2.record_learning(
        topic="routing",
        key=key,
        value=value,
        category="effectiveness",
        source="hook:routing-decision-recorder",
    )


def _seed() -> None:
    _record("golang-general-engineer:go-patterns", "request: fix | tool_errors: 1 | llm_override: 1")
    _record("golang-general-engineer:testing", "request: test | tool_errors: 0 | force_used: 1")
    _record("python-general-engineer:testing", "request: py | tool_errors: 0")
    # Bookkeeping rows the recorder stores under the same topic and category.
    _record("stack-usage:testing", "stack-usage: skill=testing")
    _record("fallback-reason:no-specialist-match", "fallback-reason: no-specialist-match")


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=15,
    )


def _json(*args: str) -> dict:
    res = _run_cli("route-stats", *args, "--json")
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_by_agent_ignores_bookkeeping_rows() -> None:
    _seed()

    res = _run_cli("route-stats", "--by", "agent")

    assert res.returncode == 0, res.stderr
    assert "stack-usage" not in res.stdout
    assert "fallback-reason" not in res.stdout
    assert "(3 total routes)" in res.stdout
    assert "golang-general-engineer" in res.stdout


def test_by_agent_json_is_only_json() -> None:
    _seed()

    report = _json("--by", "agent")

    assert report == {
        "by": "agent",
        "total_routes": 3,
        "counts": [
            {"name": "golang-general-engineer", "count": 2},
            {"name": "python-general-engineer", "count": 1},
        ],
    }


def test_by_skill_json_counts_skills() -> None:
    _seed()

    report = _json("--by", "skill")

    assert report["counts"] == [{"name": "testing", "count": 2}, {"name": "go-patterns", "count": 1}]


def test_totals_json_exclude_bookkeeping_rows() -> None:
    _seed()

    assert _json("--by", "force-route") == {"by": "force-route", "total_routes": 3, "force_routed": 1, "scored": 2}
    assert _json("--by", "override") == {"by": "override", "total_routes": 3, "llm_override": 1, "phase0_as_is": 2}
    assert _json("--by", "errors") == {
        "by": "errors",
        "total_routes": 3,
        "errored": [{"key": "golang-general-engineer:go-patterns", "request": "fix"}],
    }


def test_json_with_no_routes_is_an_empty_report() -> None:
    _record("stack-usage:testing", "stack-usage: skill=testing")

    assert _json("--by", "agent") == {"by": "agent", "total_routes": 0, "counts": []}


def test_human_output_with_only_bookkeeping_rows_reports_no_data() -> None:
    _record("stack-usage:testing", "stack-usage: skill=testing")

    res = _run_cli("route-stats", "--by", "agent")

    assert res.returncode == 0, res.stderr
    assert "No routing data found" in res.stdout

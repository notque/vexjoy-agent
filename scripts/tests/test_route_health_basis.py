#!/usr/bin/env python3
"""Tests for route-health outcome-basis reporting (ADR: silent-failure-outcome-quality).

route-health reports outcome coverage but cannot tell a silent success from a
silent failure — both score the same. This PR adds the basis split, the
silent-success share, and a coverage line. These tests drive the rendering:
seeded basis counts produce the split/shares; zero counts produce the no-data
fallback with no divide-by-zero; --json carries the structured values.

Runs route-health as a subprocess against a throwaway learning.db
(CLAUDE_LEARNING_DIR) so the real DB is never touched.

Run with: python3 -m pytest scripts/tests/test_route_health_basis.py -v
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLI = REPO_ROOT / "scripts" / "learning-db.py"
LIB_DIR = REPO_ROOT / "hooks" / "lib"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Throwaway learning.db; return a helper bound to it."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    sys.path.insert(0, str(LIB_DIR))
    import learning_db_v2 as ldb

    monkeypatch.setattr(ldb, "_initialized", False, raising=False)
    ldb.init_db()
    return {"db_dir": db_dir, "ldb": ldb, "env_dir": str(db_dir)}


def _seed_route(ldb, key: str, *, success: int = 0, failure: int = 0) -> None:
    """Create a routing row and set its success/failure counts via boost/decay."""
    ldb.record_learning(
        topic="routing",
        key=key,
        value=f"routing-decision: {key}",
        category="effectiveness",
        source="test:route-health",
    )
    for _ in range(success):
        ldb.boost_confidence("routing", key, delta=0.05)
    for _ in range(failure):
        ldb.decay_confidence("routing", key, delta=0.08)


def _seed_basis(ldb, key: str, basis: str, n: int) -> None:
    with ldb.get_connection() as conn:
        conn.execute(
            "INSERT INTO routing_outcome_basis (key, basis, count) VALUES (?,?,?) "
            "ON CONFLICT(key, basis) DO UPDATE SET count = count + ?",
            (key, basis, n, n),
        )
        conn.commit()


def _run(env_dir: str, *extra: str) -> subprocess.CompletedProcess:
    env = {"CLAUDE_LEARNING_DIR": env_dir}
    import os

    full = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(CLI), "route-health", *extra],
        capture_output=True,
        text=True,
        env=full,
    )


# --- human output: basis split + shares + coverage --------------------------


def test_human_renders_split_and_shares(db_env):
    ldb = db_env["ldb"]
    _seed_route(ldb, "a:b", success=3)
    _seed_route(ldb, "c:d", failure=1)
    _seed_basis(ldb, "a:b", "default_no_complaint", 3)
    _seed_basis(ldb, "c:d", "tool_errors_only", 1)
    _seed_basis(ldb, "c:d", "rejection_detected", 1)

    res = _run(db_env["env_dir"])
    assert res.returncode == 0, res.stderr
    out = res.stdout
    # Existing three lines unchanged + present.
    assert "Route Health:" in out
    assert "Confidence:" in out
    assert "Feedback loop:" in out
    # New lines.
    assert "Outcome basis:" in out
    assert "strong-feedback" in out and "default-success" in out
    assert "Silent-success share:" in out
    assert "Governed-path coverage:" in out
    # 2 strong (1 tool_errors + 1 rejection) vs 3 default.
    assert "2 strong-feedback vs 3 default-success" in out


def test_human_no_basis_data_fallback(db_env):
    ldb = db_env["ldb"]
    _seed_route(ldb, "a:b", success=1)  # has an outcome, but NO basis counts

    res = _run(db_env["env_dir"])
    assert res.returncode == 0, res.stderr
    out = res.stdout
    assert "Outcome basis: no basis data yet" in out
    # No share line, no divide-by-zero crash.
    assert "Silent-success share:" not in out


# --- json output ------------------------------------------------------------


def test_json_carries_basis_and_shares(db_env):
    ldb = db_env["ldb"]
    _seed_route(ldb, "a:b", success=2)
    _seed_route(ldb, "c:d", failure=1)
    _seed_basis(ldb, "a:b", "default_no_complaint", 2)
    _seed_basis(ldb, "c:d", "tool_errors_only", 1)

    res = _run(db_env["env_dir"], "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["basis"]["default_no_complaint"] == 2
    assert data["basis"]["tool_errors_only"] == 1
    assert data["basis"]["rejection_detected"] == 0
    assert data["strong_feedback"] == 1
    assert data["default_success"] == 2
    # 2 default of 3 total basis-scored outcomes.
    assert data["silent_success_share"] == pytest.approx(2 / 3)
    assert "governed_path_coverage" in data


def test_json_zero_basis_no_divide_by_zero(db_env):
    ldb = db_env["ldb"]
    _seed_route(ldb, "a:b", success=1)

    res = _run(db_env["env_dir"], "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["basis"] == {
        "rejection_detected": 0,
        "tool_errors_only": 0,
        "acceptance_detected": 0,
        "default_no_complaint": 0,
    }
    assert data["silent_success_share"] is None

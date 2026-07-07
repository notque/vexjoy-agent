#!/usr/bin/env python3
"""Tests for evidence query subcommands in scripts/learning-db.py."""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "hooks" / "lib"
SCRIPT_PATH = str(REPO_ROOT / "scripts" / "learning-db.py")
sys.path.insert(0, str(LIB_DIR))


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(tmp_path))
    import learning_db_v2

    importlib.reload(learning_db_v2)
    learning_db_v2.init_db()
    learning_db_v2.record_evidence_route_decision(
        session_id="s1",
        agent="python-general-engineer",
        skill="test-driven-development",
        complexity="Medium",
        model="gpt-5-codex",
        request_snippet="Implement evidence queries.",
        stack=["objective-loop"],
        health=0.9,
        n=8,
        failure=False,
        action="keep",
        outcome="success",
        outcome_basis="acceptance_detected",
    )
    learning_db_v2.record_evidence_event(
        event_type="tool_failure",
        source="test",
        session_id="s1",
        project_path="/repo",
        tool_name="pytest",
        action="run",
        target="scripts/tests/test_learning_db_evidence_cli.py",
        success=False,
        error="assertion failed",
    )
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


def test_evidence_recent_json(isolated_db):
    p = _run_cli("evidence-recent", "--json", "--limit", "5")
    assert p.returncode == 0, p.stderr
    rows = json.loads(p.stdout)
    assert rows[0]["event_type"] == "tool_failure"
    assert any(row["event_type"] == "route_decision" for row in rows)


def test_evidence_route_context_json(isolated_db):
    p = _run_cli("evidence-route-context", "python-general-engineer:test-driven-development", "--json")
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["totals"]["decisions"] == 1
    assert data["totals"]["successes"] == 1


def test_evidence_file_history_json(isolated_db):
    p = _run_cli(
        "evidence-file-history",
        "scripts/tests/test_learning_db_evidence_cli.py",
        "--json",
    )
    assert p.returncode == 0, p.stderr
    rows = json.loads(p.stdout)
    assert rows[0]["tool_name"] == "pytest"


def test_evidence_failures_json(isolated_db):
    p = _run_cli("evidence-failures", "--json")
    assert p.returncode == 0, p.stderr
    rows = json.loads(p.stdout)
    assert rows[0]["error"] == "assertion failed"


def test_evidence_decide_json(isolated_db):
    p = _run_cli("evidence-decide", "python-general-engineer:test-driven-development", "--json")
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["recommendation"] == "keep"
    assert data["route_key"] == "python-general-engineer:test-driven-development"

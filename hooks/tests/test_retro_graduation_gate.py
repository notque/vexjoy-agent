#!/usr/bin/env python3
"""Tests for hooks/retro-graduation-gate.py category and verification filtering.

The gate must count only categories the retro skill can graduate
(design, gotcha — see skills/meta/retro/SKILL.md, candidate query),
and only rows confirmed by an executed check (success_count >= 1).
Recurrence alone can entrench a wrong guess (docs/PHILOSOPHY.md,
"memory needs a verify step"). Unverified design/gotcha rows are
listed separately as "needs verification", never as graduatable.
Injection-only rows (error, effectiveness) and voice corpus rows must
not trip either list.

Run with: python3 -m pytest hooks/tests/test_retro_graduation_gate.py -v
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = str(_repo_root / "hooks" / "retro-graduation-gate.py")

PR_EVENT = json.dumps(
    {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_result": {"output": "https://github.com/notque/vexjoy-agent/pull/42"},
    }
)


@pytest.fixture()
def env(tmp_path: Path) -> dict:
    """Isolated env: temp learning dir + temp toolkit-shaped project dir."""
    learning_dir = tmp_path / "learning"
    learning_dir.mkdir()
    project_dir = tmp_path / "project"
    (project_dir / "agents").mkdir(parents=True)
    (project_dir / "skills").mkdir()
    e = os.environ.copy()
    e["CLAUDE_LEARNING_DIR"] = str(learning_dir)
    e["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return e


def _init_db(env: dict) -> Path:
    db_path = Path(env["CLAUDE_LEARNING_DIR"]) / "learning.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT NOT NULL DEFAULT 'test',
                success_count INTEGER DEFAULT 0,
                last_seen TEXT DEFAULT (datetime('now')),
                graduated_to TEXT,
                UNIQUE(topic, key)
            )
            """
        )
    return db_path


def _insert(
    env: dict,
    topic: str,
    key: str,
    category: str,
    confidence: float = 0.9,
    graduated_to: str | None = None,
    success_count: int = 0,
) -> None:
    db_path = Path(env["CLAUDE_LEARNING_DIR"]) / "learning.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO learnings
                (topic, key, value, category, confidence, graduated_to, success_count, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (topic, key, f"value for {key}", category, confidence, graduated_to, success_count),
        )


def _run_hook(env: dict, stdin: str = PR_EVENT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, HOOK_PATH],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def test_error_rows_do_not_trip_gate(env):
    """Injection-only 'error' rows are not graduation candidates, even verified."""
    _init_db(env)
    _insert(env, "debugging", "missing-import", "error", confidence=0.95, success_count=3)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" not in result.stdout


def test_voice_rows_do_not_trip_gate(env):
    """Voice corpus rows are not graduation candidates."""
    _init_db(env)
    _insert(env, "voice-fixture", "phrase-cadence", "voice", confidence=0.9, success_count=2)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" not in result.stdout


def test_effectiveness_rows_do_not_trip_gate(env):
    """Routing 'effectiveness' rows are not graduation candidates."""
    _init_db(env)
    _insert(env, "routing", "agent-skill-pair", "effectiveness", confidence=0.9, success_count=2)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" not in result.stdout


def test_verified_gotcha_row_trips_gate(env):
    """A verified (success_count >= 1) ungraduated gotcha triggers the graduation advisory."""
    _init_db(env)
    _insert(env, "go-patterns", "mutex-state-machine", "gotcha", confidence=0.8, success_count=1)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" in result.stdout
    assert "go-patterns" in result.stdout
    assert "mutex-state-machine" in result.stdout


def test_verified_design_row_trips_gate(env):
    """A verified ungraduated design row triggers the graduation advisory."""
    _init_db(env)
    _insert(env, "hooks", "atomic-write-pattern", "design", confidence=0.75, success_count=2)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" in result.stdout


def test_unverified_gotcha_is_not_graduatable(env):
    """An unverified (success_count = 0) gotcha is listed as needs-verification, not graduatable."""
    _init_db(env)
    _insert(env, "go-patterns", "unconfirmed-guess", "gotcha", confidence=0.9, success_count=0)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" in result.stdout
    assert "unconfirmed-guess" in result.stdout


def test_unverified_design_is_not_graduatable(env):
    """An unverified design row is listed as needs-verification, not graduatable."""
    _init_db(env)
    _insert(env, "hooks", "untested-pattern", "design", confidence=0.85, success_count=0)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" in result.stdout


def test_mixed_rows_split_into_both_sections(env):
    """Verified and unverified rows appear in their own sections of one advisory."""
    _init_db(env)
    _insert(env, "hooks", "proven-pattern", "design", confidence=0.8, success_count=1)
    _insert(env, "hooks", "unproven-pattern", "gotcha", confidence=0.8, success_count=0)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" in result.stdout
    assert "proven-pattern" in result.stdout
    assert "needs verification" in result.stdout
    assert "unproven-pattern" in result.stdout


def test_graduated_design_row_does_not_trip_gate(env):
    """Already-graduated rows are excluded from both sections."""
    _init_db(env)
    _insert(env, "hooks", "done-pattern", "design", confidence=0.9, graduated_to="agents/x.md", success_count=1)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" not in result.stdout


def test_low_confidence_gotcha_does_not_trip_gate(env):
    """Rows below the 0.7 confidence threshold are excluded from both sections."""
    _init_db(env)
    _insert(env, "hooks", "weak-finding", "gotcha", confidence=0.5, success_count=1)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout
    assert "needs verification" not in result.stdout


def test_empty_db_is_safe(env):
    """A DB with no rows produces no advisory and exits 0."""
    _init_db(env)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_missing_db_is_safe(env):
    """No learning.db at all: silent, exit 0."""
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_advisory_never_blocks(env):
    """Advisory contract: exit 0 even when the gate fires, output is valid JSON without a block decision."""
    _init_db(env)
    _insert(env, "go-patterns", "mutex-state-machine", "gotcha", confidence=0.8, success_count=1)
    result = _run_hook(env)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("decision") != "block"


def test_needs_verification_advisory_never_blocks(env):
    """Needs-verification advisory is also non-blocking valid JSON."""
    _init_db(env)
    _insert(env, "hooks", "unproven-pattern", "design", confidence=0.8, success_count=0)
    result = _run_hook(env)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("decision") != "block"


def test_malformed_stdin_exits_zero(env):
    """Garbage input must not break the hook."""
    result = _run_hook(env, stdin="not json")
    assert result.returncode == 0

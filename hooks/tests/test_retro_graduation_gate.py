#!/usr/bin/env python3
"""Tests for hooks/retro-graduation-gate.py category filtering.

The gate must count only categories the retro skill can graduate
(design, gotcha — see skills/meta/retro/SKILL.md, candidate query).
Injection-only rows (error, effectiveness) and voice corpus rows must
not trip it.

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
                last_seen TEXT DEFAULT (datetime('now')),
                graduated_to TEXT,
                UNIQUE(topic, key)
            )
            """
        )
    return db_path


def _insert(
    env: dict, topic: str, key: str, category: str, confidence: float = 0.9, graduated_to: str | None = None
) -> None:
    db_path = Path(env["CLAUDE_LEARNING_DIR"]) / "learning.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO learnings (topic, key, value, category, confidence, graduated_to, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (topic, key, f"value for {key}", category, confidence, graduated_to),
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
    """Injection-only 'error' rows are not graduation candidates."""
    _init_db(env)
    _insert(env, "debugging", "missing-import", "error", confidence=0.95)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_voice_rows_do_not_trip_gate(env):
    """Voice corpus rows are not graduation candidates."""
    _init_db(env)
    _insert(env, "voice-amy", "phrase-cadence", "voice", confidence=0.9)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_effectiveness_rows_do_not_trip_gate(env):
    """Routing 'effectiveness' rows are not graduation candidates."""
    _init_db(env)
    _insert(env, "routing", "agent-skill-pair", "effectiveness", confidence=0.9)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_gotcha_row_trips_gate(env):
    """An ungraduated high-confidence gotcha row triggers the advisory."""
    _init_db(env)
    _insert(env, "go-patterns", "mutex-state-machine", "gotcha", confidence=0.8)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" in result.stdout
    assert "go-patterns" in result.stdout
    assert "mutex-state-machine" in result.stdout


def test_design_row_trips_gate(env):
    """An ungraduated high-confidence design row triggers the advisory."""
    _init_db(env)
    _insert(env, "hooks", "atomic-write-pattern", "design", confidence=0.75)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" in result.stdout


def test_graduated_design_row_does_not_trip_gate(env):
    """Already-graduated rows are excluded."""
    _init_db(env)
    _insert(env, "hooks", "done-pattern", "design", confidence=0.9, graduated_to="agents/x.md")
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


def test_low_confidence_gotcha_does_not_trip_gate(env):
    """Rows below the 0.7 confidence threshold are excluded."""
    _init_db(env)
    _insert(env, "hooks", "weak-finding", "gotcha", confidence=0.5)
    result = _run_hook(env)
    assert result.returncode == 0
    assert "ungraduated" not in result.stdout


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
    _insert(env, "go-patterns", "mutex-state-machine", "gotcha", confidence=0.8)
    result = _run_hook(env)
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload.get("decision") != "block"


def test_malformed_stdin_exits_zero(env):
    """Garbage input must not break the hook."""
    result = _run_hook(env, stdin="not json")
    assert result.returncode == 0

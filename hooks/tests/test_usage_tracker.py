#!/usr/bin/env python3
"""Tests for the usage-tracker PostToolUse hook.

Covers:
- Skill invocations record skill_name from tool_input.skill.
- Agent invocations record agent_type from tool_input.subagent_type.
- Events using the "input" key instead of "tool_input" still record correctly
  (the field-name fallback that fixed the 17% unknown gap).
- Empty/malformed events exit 0 without error.

Uses a throwaway usage.db and learning.db via CLAUDE_LEARNING_DIR.

Run with: python3 -m pytest hooks/tests/test_usage_tracker.py -v
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
LIB_DIR = HOOKS_DIR / "lib"
HOOK_PATH = HOOKS_DIR / "usage-tracker.py"


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Point both databases at a throwaway directory."""
    db_dir = tmp_path / "learning"
    db_dir.mkdir()
    monkeypatch.setenv("CLAUDE_LEARNING_DIR", str(db_dir))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-ut")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/test-project")
    sys.path.insert(0, str(LIB_DIR))
    # Initialize usage.db
    import usage_db

    usage_db.init_db()
    yield {"db_dir": db_dir}


def _run_hook(event: dict, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook as a subprocess feeding the event on stdin."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
    )


def _skill_event(skill_name="testing", args="some args"):
    """Build a PostToolUse:Skill event with tool_input."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "session_id": "test-session-ut",
        "tool_input": {
            "skill": skill_name,
            "args": args,
        },
    }


def _skill_event_input_key(skill_name="testing", args="some args"):
    """Build a PostToolUse:Skill event with 'input' instead of 'tool_input'.

    Some harness versions use "input" as the field name. The tracker must
    handle both to avoid recording skill_name="unknown".
    """
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Skill",
        "session_id": "test-session-ut",
        "input": {
            "skill": skill_name,
            "args": args,
        },
    }


def _agent_event(agent_type="python-general-engineer", description="do work"):
    """Build a PostToolUse:Agent event with tool_input."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": "test-session-ut",
        "tool_input": {
            "subagent_type": agent_type,
            "description": description,
        },
    }


def _agent_event_input_key(agent_type="python-general-engineer", description="do work"):
    """Build a PostToolUse:Agent event with 'input' instead of 'tool_input'."""
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Agent",
        "session_id": "test-session-ut",
        "input": {
            "subagent_type": agent_type,
            "description": description,
        },
    }


class TestSkillRecording:
    """Skill invocation recording — the unknown-name fix."""

    def test_skill_records_name_from_tool_input(self, db_env):
        """Standard event shape: tool_input.skill is read."""
        result = _run_hook(
            _skill_event("frontend"),
            {"CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

        conn = sqlite3.connect(db_env["db_dir"] / "usage.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT skill_name FROM skill_invocations").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["skill_name"] == "frontend"

    def test_skill_records_name_from_input_key(self, db_env):
        """Alternate event shape: input.skill is read (was the unknown bug)."""
        result = _run_hook(
            _skill_event_input_key("browser-jev-automation"),
            {"CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

        conn = sqlite3.connect(db_env["db_dir"] / "usage.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT skill_name FROM skill_invocations").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["skill_name"] == "browser-jev-automation"

    def test_skill_unknown_when_both_keys_missing(self, db_env):
        """No tool_input or input => skill_name defaults to 'unknown'."""
        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "session_id": "test-session-ut",
        }
        result = _run_hook(
            event,
            {"CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

        conn = sqlite3.connect(db_env["db_dir"] / "usage.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT skill_name FROM skill_invocations").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["skill_name"] == "unknown"


class TestAgentRecording:
    """Agent invocation recording — same field-name fallback."""

    def test_agent_records_type_from_tool_input(self, db_env):
        result = _run_hook(
            _agent_event("golang-general-engineer", "fix the thing"),
            {"CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

        conn = sqlite3.connect(db_env["db_dir"] / "usage.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT agent_type, description FROM agent_invocations").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["agent_type"] == "golang-general-engineer"
        assert rows[0]["description"] == "fix the thing"

    def test_agent_records_type_from_input_key(self, db_env):
        result = _run_hook(
            _agent_event_input_key("ui-frontend-engineer", "build page"),
            {"CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

        conn = sqlite3.connect(db_env["db_dir"] / "usage.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT agent_type, description FROM agent_invocations").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["agent_type"] == "ui-frontend-engineer"


class TestNonBlocking:
    """Hook must exit 0 on every input shape."""

    def test_empty_input(self, db_env):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

    def test_malformed_json(self, db_env):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not json",
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
        )
        assert result.returncode == 0

    def test_no_stdin(self, db_env):
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=None,
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_LEARNING_DIR": str(db_env["db_dir"])},
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0

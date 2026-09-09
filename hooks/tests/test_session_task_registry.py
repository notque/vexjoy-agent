"""Tests for the session-task-registry hook."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import importlib

# Import the module with hyphenated name
spec = importlib.util.spec_from_file_location(
    "session_task_registry",
    Path(__file__).resolve().parent.parent / "session-task-registry.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def tmp_registry(tmp_path):
    """Patch REGISTRY_PATH to a temp file."""
    registry_file = tmp_path / "task-registry.json"
    with patch.object(mod, "REGISTRY_PATH", registry_file):
        yield registry_file


def test_empty_registry_creation(tmp_registry):
    """Loading a non-existent registry returns empty structure."""
    reg = mod._load_registry()
    assert reg == {"version": 1, "tasks": []}


def test_task_recording_from_do_route_marker(tmp_registry):
    """PostToolUse records a task when [do-route] marker is present."""
    event = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "[do-route] agent=python-general-engineer skill=test-driven-development complexity=medium\nFix the bug",
            "description": "Fix the test bug",
        },
        "session_id": "test-session-1",
    }
    mod.handle_post_tool_use(event)

    reg = mod._load_registry()
    assert len(reg["tasks"]) == 1
    task = reg["tasks"][0]
    assert task["agent"] == "python-general-engineer"
    assert task["skill"] == "test-driven-development"
    assert task["complexity"] == "medium"
    assert task["status"] == "dispatched"
    assert task["session_id"] == "test-session-1"
    assert "Fix the test bug" in task["summary"]


def test_session_start_injection_with_incomplete(tmp_registry, capsys):
    """SessionStart injects context when incomplete tasks exist."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "golang-general-engineer",
                "skill": "go-patterns",
                "complexity": "medium",
                "summary": "Fix Go test race condition",
                "dispatched_at": "2026-09-08T10:00:00+00:00",
                "completed_at": None,
                "status": "dispatched",
                "session_id": "old-session",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    with pytest.raises(SystemExit):
        mod.handle_session_start()

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "[task-registry]" in ctx
    assert "260908-001" in ctx
    assert "Fix Go test race condition" in ctx


def test_subagent_stop_updates_status(tmp_registry):
    """SubagentStop updates the task status to completed."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "python-general-engineer",
                "skill": "",
                "complexity": "simple",
                "summary": "Quick fix",
                "dispatched_at": "2026-09-08T10:00:00+00:00",
                "completed_at": None,
                "status": "dispatched",
                "session_id": "sess-1",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    event = {"session_id": "sess-1", "hook_event_name": "SubagentStop"}
    mod.handle_subagent_stop(event)

    reg = mod._load_registry()
    assert reg["tasks"][0]["status"] == "completed"
    assert reg["tasks"][0]["completed_at"] is not None


def test_atomic_write(tmp_registry):
    """Registry file is written atomically with correct permissions."""
    registry = {"version": 1, "tasks": []}
    mod._save_registry(registry)

    assert tmp_registry.exists()
    # Check permissions (0600)
    stat = os.stat(tmp_registry)
    assert oct(stat.st_mode & 0o777) == "0o600"


def test_no_injection_when_no_incomplete(tmp_registry, capsys):
    """SessionStart produces no output when all tasks are completed."""
    registry = {
        "version": 1,
        "tasks": [
            {
                "id": "260908-001",
                "agent": "test",
                "skill": "",
                "complexity": "",
                "summary": "Done task",
                "dispatched_at": "2026-09-08T10:00:00+00:00",
                "completed_at": "2026-09-08T11:00:00+00:00",
                "status": "completed",
                "session_id": "old",
            }
        ],
    }
    tmp_registry.write_text(json.dumps(registry))

    # Should not raise SystemExit (no output)
    mod.handle_session_start()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_skip_non_do_route_agent(tmp_registry):
    """PostToolUse skips Agent dispatches without [do-route] marker."""
    event = {
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Just a normal agent dispatch",
            "description": "Normal",
        },
        "session_id": "s1",
    }
    mod.handle_post_tool_use(event)
    reg = mod._load_registry()
    assert len(reg["tasks"]) == 0


def test_exit_code_zero():
    """Hook exits 0 on empty stdin."""
    hook_path = Path(__file__).resolve().parent.parent / "session-task-registry.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0

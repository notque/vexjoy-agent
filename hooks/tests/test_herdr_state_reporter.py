"""Tests for herdr-state-reporter hook."""

import json
import os
import subprocess
import sys

import pytest

HOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "herdr-state-reporter.py")


def run_hook(event=None, env_extra=None):
    """Run the hook as a subprocess with optional event JSON on stdin."""
    env = os.environ.copy()
    env.pop("HERDR_ENV", None)
    env.pop("HERDR_PANE_ID", None)
    if env_extra:
        env.update(env_extra)

    stdin_data = json.dumps(event) if event else ""
    return subprocess.run(
        [sys.executable, HOOK_PATH],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


class TestNoHerdrEnv:
    """When HERDR_ENV is not set, hook exits 0 with no stdout."""

    def test_exits_zero_no_output(self):
        result = run_hook(event={"hook_event_name": "SessionStart"})
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestHerdrMissingBinary:
    """When HERDR_ENV=1 but herdr binary is missing, hook exits 0."""

    def test_exits_zero_when_binary_missing(self):
        env = {"HERDR_ENV": "1", "HERDR_PANE_ID": "test-pane", "PATH": "/nonexistent"}
        result = run_hook(
            event={"hook_event_name": "SessionStart"},
            env_extra=env,
        )
        assert result.returncode == 0


class TestSessionStart:
    """SessionStart event produces context injection."""

    def test_session_start_injects_context(self):
        env = {"HERDR_ENV": "1", "HERDR_PANE_ID": "test-pane", "PATH": "/nonexistent"}
        result = run_hook(
            event={"hook_event_name": "SessionStart"},
            env_extra=env,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "hookSpecificOutput" in output
        hso = output["hookSpecificOutput"]
        assert hso["hookEventName"] == "SessionStart"
        assert "herdr" in hso.get("additionalContext", "").lower()


class TestSubagentStop:
    """SubagentStop event reports state based on subagent status."""

    def test_subagent_stop_exits_zero(self):
        env = {"HERDR_ENV": "1", "HERDR_PANE_ID": "test-pane", "PATH": "/nonexistent"}
        result = run_hook(
            event={"hook_event_name": "SubagentStop", "subagent_result": {}},
            env_extra=env,
        )
        assert result.returncode == 0

    def test_blocked_subagent(self):
        env = {"HERDR_ENV": "1", "HERDR_PANE_ID": "test-pane", "PATH": "/nonexistent"}
        result = run_hook(
            event={
                "hook_event_name": "SubagentStop",
                "subagent_result": {"blocked": True},
            },
            env_extra=env,
        )
        assert result.returncode == 0

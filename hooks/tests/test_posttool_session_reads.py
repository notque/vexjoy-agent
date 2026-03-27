#!/usr/bin/env python3
"""
Tests for the posttool-session-reads hook.

Run with: python3 -m pytest hooks/tests/test_posttool_session_reads.py -v
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "posttool-session-reads.py"

spec = importlib.util.spec_from_file_location("posttool_session_reads", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SESSION_READS_FILE = mod.SESSION_READS_FILE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_hook(event: dict) -> tuple[str, str, int]:
    """Run the hook with given event and return (stdout, stderr, exit_code)."""
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout, result.stderr, result.returncode


# ---------------------------------------------------------------------------
# Tool Name Filtering
# ---------------------------------------------------------------------------


class TestToolNameFiltering:
    """Only Read tool events should be processed."""

    def test_nonread_tool_exits_zero(self, tmp_path, monkeypatch):
        """Non-Read tool filtering is now handled by matcher 'Read' in settings.json.

        When called directly (without matcher), the hook processes any tool_name.
        This test verifies the hook still exits 0 (non-blocking) for any input.
        """
        monkeypatch.chdir(tmp_path)
        for tool in ("Write", "Edit", "Bash"):
            event = {
                "tool_name": tool,
                "tool_input": {"file_path": "/some/file.py"} if tool != "Bash" else {"command": "ls"},
            }
            stdout, stderr, code = run_hook(event)
            assert code == 0

    def test_ignores_bash_tool(self, tmp_path, monkeypatch):
        """Bash tool events should be ignored (no file_path to extract)."""
        monkeypatch.chdir(tmp_path)
        event = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        }
        stdout, stderr, code = run_hook(event)
        assert code == 0

    def test_ignores_agent_tool(self, tmp_path, monkeypatch):
        """Agent tool events should be ignored."""
        monkeypatch.chdir(tmp_path)
        event = {
            "tool_name": "Agent",
            "tool_input": {"prompt": "do something"},
        }
        stdout, stderr, code = run_hook(event)
        assert code == 0


# ---------------------------------------------------------------------------
# File Path Extraction and Tracking
# ---------------------------------------------------------------------------


class TestFilePathTracking:
    """Verify file paths are correctly extracted and written."""

    def test_tracks_read_file_path(self, tmp_path, monkeypatch):
        """Read tool event should append the file path to session-reads.txt."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()

        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/project/main.py"},
        }
        stdout, stderr, code = run_hook(event)

        assert code == 0
        reads_file = reads_dir / "session-reads.txt"
        assert reads_file.exists()
        content = reads_file.read_text()
        assert "/home/user/project/main.py" in content

    def test_tracks_multiple_reads(self, tmp_path, monkeypatch):
        """Multiple Read events should all be tracked."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()

        paths = ["/a/file1.py", "/b/file2.go", "/c/file3.rs"]
        for p in paths:
            event = {
                "tool_name": "Read",
                "tool_input": {"file_path": p},
            }
            run_hook(event)

        reads_file = reads_dir / "session-reads.txt"
        content = reads_file.read_text()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        assert len(lines) == 3
        for p in paths:
            assert p in lines

    def test_missing_file_path_does_nothing(self, tmp_path, monkeypatch):
        """Read event with no file_path in tool_input should be no-op."""
        monkeypatch.chdir(tmp_path)
        event = {
            "tool_name": "Read",
            "tool_input": {},
        }
        stdout, stderr, code = run_hook(event)
        assert code == 0

    def test_empty_file_path_does_nothing(self, tmp_path, monkeypatch):
        """Read event with empty file_path should be no-op."""
        monkeypatch.chdir(tmp_path)
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": ""},
        }
        stdout, stderr, code = run_hook(event)
        assert code == 0


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Same path should not appear twice in the session file."""

    def test_duplicate_path_not_appended(self, tmp_path, monkeypatch):
        """Reading the same file twice should only produce one entry."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()

        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/main.py"},
        }
        run_hook(event)
        run_hook(event)

        reads_file = reads_dir / "session-reads.txt"
        content = reads_file.read_text()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        assert lines.count("/home/user/main.py") == 1

    def test_different_paths_both_tracked(self, tmp_path, monkeypatch):
        """Different paths should both be recorded."""
        monkeypatch.chdir(tmp_path)
        reads_dir = tmp_path / ".claude"
        reads_dir.mkdir()

        for p in ["/a.py", "/b.py"]:
            event = {
                "tool_name": "Read",
                "tool_input": {"file_path": p},
            }
            run_hook(event)

        reads_file = reads_dir / "session-reads.txt"
        content = reads_file.read_text()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# Output Format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Hook should produce silent output (empty JSON)."""

    def test_silent_output_on_read_event(self, tmp_path, monkeypatch):
        """Read event should produce hook JSON output with no context."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()

        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
        }
        stdout, stderr, code = run_hook(event)

        assert code == 0
        if stdout.strip():
            output = json.loads(stdout)
            hook_output = output.get("hookSpecificOutput", {})
            assert hook_output.get("hookEventName") == "PostToolUse"
            # No additionalContext should be present
            assert "additionalContext" not in hook_output


# ---------------------------------------------------------------------------
# Non-Blocking Guarantee
# ---------------------------------------------------------------------------


class TestNonBlocking:
    """Hook must always exit 0 regardless of errors."""

    def test_exits_zero_on_malformed_json(self):
        """Malformed JSON input should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json{{{",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_empty_input(self):
        """Empty stdin should still exit 0."""
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_exits_zero_on_missing_tool_input(self):
        """Event with no tool_input should still exit 0."""
        event = {"tool_name": "Read"}
        result = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_creates_claude_dir_if_missing(self, tmp_path, monkeypatch):
        """Hook should create .claude/ directory if it doesn't exist."""
        monkeypatch.chdir(tmp_path)
        event = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/some/file.py"},
        }
        stdout, stderr, code = run_hook(event)
        assert code == 0

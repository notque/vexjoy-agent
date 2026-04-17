#!/usr/bin/env python3
"""Tests for the record-activation PostToolUse hook.

Run with: python3 -m pytest hooks/tests/test_record_activation.py -v
"""

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "record-activation.py"

spec = importlib.util.spec_from_file_location("record_activation", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)

# Prevent sys.exit from killing the test runner
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Provide a unique session ID and patch /tmp paths to use tmp_path."""
    session_id = "test-activation-session-001"
    monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

    # Patch Path so /tmp marker/counter files go to tmp_path
    original_truediv = Path.__truediv__

    def patched_truediv(self: Path, other: str) -> Path:
        if str(self) == "/tmp" and "claude-" in str(other):
            return tmp_path / other
        return original_truediv(self, other)

    monkeypatch.setattr(Path, "__truediv__", patched_truediv)
    return session_id


def _make_hook_input(tool_name: str = "Bash", is_error: bool = False, output: str = "ok") -> str:
    """Build JSON hook input string."""
    return json.dumps({"tool_name": tool_name, "tool_result": {"output": output, "is_error": is_error}})


# ---------------------------------------------------------------------------
# Tests: Tool filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    """Verify only Edit/Write/Bash tools are tracked."""

    def test_skips_read_tool(self, tmp_session: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(tool_name="Read")
            mod.main()
            mock_run.assert_not_called()

    def test_skips_grep_tool(self, tmp_session: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(tool_name="Grep")
            mod.main()
            mock_run.assert_not_called()

    def test_skips_glob_tool(self, tmp_session: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(tool_name="Glob")
            mod.main()
            mock_run.assert_not_called()

    def test_skips_error_results(self, tmp_session: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(is_error=True)
            mod.main()
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Batching
# ---------------------------------------------------------------------------


class TestBatching:
    """Verify only every 10th successful call triggers recording."""

    def test_no_record_before_10th_call(self, tmp_session: str, tmp_path: Path) -> None:
        """Calls 1-9 should not trigger subprocess."""
        for i in range(1, 10):
            with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
                mock_stdin.read.return_value = _make_hook_input()
                mod.main()
                if i < 10:
                    mock_run.assert_not_called()

    def test_records_on_10th_call(self, tmp_session: str, tmp_path: Path) -> None:
        """The 10th call should trigger a record-session subprocess."""
        # Set counter to 9 so next call is the 10th
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "record-session" in cmd


# ---------------------------------------------------------------------------
# Tests: Retro knowledge detection
# ---------------------------------------------------------------------------


class TestRetroDetection:
    """Verify --had-retro flag is passed only when marker exists."""

    def test_had_retro_flag_when_marker_exists(self, tmp_session: str, tmp_path: Path) -> None:
        # Set counter to 9 and create retro marker
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")
        marker = tmp_path / f"claude-retro-active-{tmp_session}"
        marker.write_text("1")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            cmd = mock_run.call_args[0][0]
            assert "--had-retro" in cmd

    def test_no_retro_flag_without_marker(self, tmp_session: str, tmp_path: Path) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            cmd = mock_run.call_args[0][0]
            assert "--had-retro" not in cmd


# ---------------------------------------------------------------------------
# Tests: Error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Verify hook never blocks on errors."""

    def test_invalid_json_exits_cleanly(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = "not json"
            mod.main()
            mock_exit.assert_called_with(0)

    def test_subprocess_timeout_exits_cleanly(self, tmp_session: str, tmp_path: Path) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=5)),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit") as mock_exit,
        ):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            mock_exit.assert_called_with(0)

    def test_missing_script_exits_cleanly(self, tmp_session: str, tmp_path: Path) -> None:
        counter_file = tmp_path / f"claude-activation-counter-{tmp_session}"
        counter_file.write_text("9")

        with (
            patch.object(Path, "exists", return_value=False),
            patch("subprocess.run") as mock_run,
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit"),
        ):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            mock_run.assert_not_called()

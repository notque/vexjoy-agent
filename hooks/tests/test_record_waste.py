#!/usr/bin/env python3
"""Tests for the record-waste PostToolUse hook.

Run with: python3 -m pytest hooks/tests/test_record_waste.py -v
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

HOOK_PATH = Path(__file__).parent.parent / "record-waste.py"

spec = importlib.util.spec_from_file_location("record_waste", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)

# Prevent sys.exit from killing the test runner
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set a stable session ID in the environment."""
    session_id = "test-waste-session-001"
    monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
    return session_id


def _make_hook_input(is_error: bool = True, output: str = "error: something failed") -> str:
    """Build JSON hook input string."""
    return json.dumps({"tool_name": "Bash", "tool_result": {"output": output, "is_error": is_error}})


# ---------------------------------------------------------------------------
# Tests: Error filtering
# ---------------------------------------------------------------------------


class TestErrorFiltering:
    """Verify only failures are tracked."""

    def test_skips_successful_tool_use(self, session_env: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(is_error=False, output="all good")
            mod.main()
            mock_run.assert_not_called()

    def test_records_on_error(self, session_env: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(is_error=True)
            mod.main()
            mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Token waste estimation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Verify waste token calculation logic."""

    def test_minimum_100_tokens_for_short_output(self, session_env: str) -> None:
        """Short error output should still register MIN_WASTE_TOKENS."""
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(output="err")
            mod.main()
            cmd = mock_run.call_args[0][0]
            tokens_idx = cmd.index("--tokens") + 1
            assert int(cmd[tokens_idx]) == 100  # MIN_WASTE_TOKENS

    def test_token_estimate_scales_with_output(self, session_env: str) -> None:
        """Longer output should produce proportionally more waste tokens."""
        long_output = "x" * 2000  # 2000 chars / 4 = 500 tokens
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(output=long_output)
            mod.main()
            cmd = mock_run.call_args[0][0]
            tokens_idx = cmd.index("--tokens") + 1
            assert int(cmd[tokens_idx]) == 500

    def test_empty_output_uses_minimum(self, session_env: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input(output="")
            mod.main()
            cmd = mock_run.call_args[0][0]
            tokens_idx = cmd.index("--tokens") + 1
            assert int(cmd[tokens_idx]) == 100


# ---------------------------------------------------------------------------
# Tests: CLI args
# ---------------------------------------------------------------------------


class TestCLIArgs:
    """Verify correct arguments are passed to learning-db.py."""

    def test_passes_session_and_tokens(self, session_env: str) -> None:
        with patch("subprocess.run") as mock_run, patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            cmd = mock_run.call_args[0][0]
            assert "record-waste" in cmd
            assert "--session" in cmd
            assert session_env in cmd
            assert "--tokens" in cmd


# ---------------------------------------------------------------------------
# Tests: Error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Verify hook never blocks on errors."""

    def test_invalid_json_exits_cleanly(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = "{invalid json"
            mod.main()
            mock_exit.assert_called_with(0)

    def test_subprocess_timeout_exits_cleanly(self, session_env: str) -> None:
        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=5)),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit") as mock_exit,
        ):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            mock_exit.assert_called_with(0)

    def test_oserror_exits_cleanly(self, session_env: str) -> None:
        with (
            patch("subprocess.run", side_effect=OSError("disk full")),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit") as mock_exit,
        ):
            mock_stdin.read.return_value = _make_hook_input()
            mod.main()
            mock_exit.assert_called_with(0)

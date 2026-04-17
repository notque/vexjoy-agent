#!/usr/bin/env python3
"""Tests for the suggest-compact PreToolUse hook.

Run with: python3 -m pytest hooks/tests/test_suggest_compact.py -v
"""

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "suggest-compact.py"

spec = importlib.util.spec_from_file_location("suggest_compact", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)

# Prevent sys.exit from killing the test runner during module load
with patch("sys.exit"):
    spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patch get_state_file in the hook module to write under tmp_path.

    get_state_file constructs Path(f"/tmp/claude-{prefix}-{session_id}.state")
    as a direct string — the /tmp __truediv__ trick does not intercept it.
    Patching the function in the module namespace is the reliable approach.
    """
    session_id = "test-compact-session-001"
    monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

    sf = tmp_path / f"claude-compact-count-{session_id}.state"

    monkeypatch.setattr(mod, "get_state_file", lambda prefix: sf)  # noqa: ARG005
    return sf


def _make_event(tool_name: str = "Edit") -> str:
    """Build a minimal PreToolUse JSON event."""
    return json.dumps({"tool_name": tool_name, "tool_input": {}})


def _set_counter(state_file: Path, value: int) -> None:
    """Pre-seed the counter state file."""
    state_file.write_text(str(value))


def _capture_stdout(event_json: str) -> str:
    """Run main() with patched stdin/exit and capture stdout."""
    buf = io.StringIO()
    with patch("sys.stdin") as mock_stdin, patch("sys.exit"), patch("sys.stdout", buf):
        mock_stdin.read.return_value = event_json
        mod.main()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests: Tool filtering
# ---------------------------------------------------------------------------


class TestToolFiltering:
    """Only Edit and Write calls should increment the counter."""

    def test_edit_increments_counter(self, state_file: Path) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_event("Edit")
            mod.main()
        assert state_file.exists()
        assert int(state_file.read_text()) == 1

    def test_write_increments_counter(self, state_file: Path) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_event("Write")
            mod.main()
        assert state_file.exists()
        assert int(state_file.read_text()) == 1

    def test_read_does_not_increment(self, state_file: Path) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_event("Read")
            mod.main()
        assert not state_file.exists()

    def test_bash_does_not_increment(self, state_file: Path) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_event("Bash")
            mod.main()
        assert not state_file.exists()

    def test_glob_does_not_increment(self, state_file: Path) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
            mock_stdin.read.return_value = _make_event("Glob")
            mod.main()
        assert not state_file.exists()


# ---------------------------------------------------------------------------
# Tests: Threshold suggestion
# ---------------------------------------------------------------------------


class TestThresholdSuggestion:
    """At threshold, a suggestion should appear in hook output."""

    def test_no_output_below_threshold(self, state_file: Path) -> None:
        # Pre-seed counter so this call becomes #49 (one below default threshold 50)
        _set_counter(state_file, 48)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext")
        assert context is None

    def test_emits_at_threshold(self, state_file: Path) -> None:
        # Pre-seed counter so this call becomes #50 (the default threshold)
        _set_counter(state_file, 49)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[strategic-compact]" in context
        assert "50 tool calls reached" in context
        assert "consider /compact" in context

    def test_no_output_just_after_threshold(self, state_file: Path) -> None:
        # Call #51 — between threshold and first reminder
        _set_counter(state_file, 50)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext")
        assert context is None

    def test_custom_threshold_via_env(self, state_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMPACT_THRESHOLD", "10")
        _set_counter(state_file, 9)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[strategic-compact]" in context
        assert "10 tool calls reached" in context

    def test_threshold_clamped_to_minimum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMPACT_THRESHOLD", "-5")
        assert mod._get_threshold() == 1

    def test_threshold_clamped_to_maximum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMPACT_THRESHOLD", "99999")
        assert mod._get_threshold() == 10000

    def test_invalid_threshold_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMPACT_THRESHOLD", "not-a-number")
        assert mod._get_threshold() == 50


# ---------------------------------------------------------------------------
# Tests: Periodic reminders
# ---------------------------------------------------------------------------


class TestPeriodicReminders:
    """Every 25 calls after threshold should emit a reminder."""

    def test_emits_at_threshold_plus_25(self, state_file: Path) -> None:
        # Call #75 (threshold=50, 75-50=25 — first reminder)
        _set_counter(state_file, 74)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[strategic-compact]" in context
        assert "75 tool calls" in context
        assert "good checkpoint" in context

    def test_emits_at_threshold_plus_50(self, state_file: Path) -> None:
        # Call #100 (threshold=50, 100-50=50 — second reminder)
        _set_counter(state_file, 99)
        output = _capture_stdout(_make_event("Write"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[strategic-compact]" in context
        assert "100 tool calls" in context

    def test_no_output_between_reminders(self, state_file: Path) -> None:
        # Call #80 — between first (75) and second (100) reminders
        _set_counter(state_file, 79)
        output = _capture_stdout(_make_event("Edit"))
        data = json.loads(output)
        context = data.get("hookSpecificOutput", {}).get("additionalContext")
        assert context is None


# ---------------------------------------------------------------------------
# Tests: Counter persistence
# ---------------------------------------------------------------------------


class TestCounterPersistence:
    """Counter should persist across sequential calls."""

    def test_counter_increments_across_calls(self, state_file: Path) -> None:
        for expected in range(1, 6):
            with patch("sys.stdin") as mock_stdin, patch("sys.exit"):
                mock_stdin.read.return_value = _make_event("Edit")
                mod.main()
            assert int(state_file.read_text()) == expected


# ---------------------------------------------------------------------------
# Tests: Fail-open / error resilience
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """Hook must never exit with code other than 0 under any input."""

    def test_invalid_json_exits_zero(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = "not valid json"
            mod.main()
        mock_exit.assert_called_with(0)

    def test_empty_stdin_exits_zero(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = ""
            mod.main()
        mock_exit.assert_called_with(0)

    def test_missing_tool_name_exits_zero(self) -> None:
        with patch("sys.stdin") as mock_stdin, patch("sys.exit") as mock_exit:
            mock_stdin.read.return_value = json.dumps({})
            mod.main()
        mock_exit.assert_called_with(0)

    def test_unhandled_exception_exits_zero(self, state_file: Path) -> None:
        """main() wraps _run() in try/finally; RuntimeError must still exit 0."""
        with (
            patch("sys.stdin") as mock_stdin,
            patch.object(mod, "_get_and_increment_count", side_effect=RuntimeError("boom")),
            patch("sys.exit") as mock_exit,
        ):
            mock_stdin.read.return_value = _make_event("Edit")
            mod.main()
        calls = [c.args[0] for c in mock_exit.call_args_list if c.args]
        assert calls, "sys.exit was never called"
        assert all(c == 0 for c in calls), f"Non-zero exit detected: {calls}"

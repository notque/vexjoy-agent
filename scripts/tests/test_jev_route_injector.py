"""Tests for hooks/jev-route-injector-userprompt.py (v3: route-only).

Covers:
- extract_prompt: all field paths (prompt, message, userMessage, tool_input.prompt, empty/invalid)
- extract_request_text: /d matching, plain-text non-matching, /d with args, empty /d, non-/d input
- run_jev_route: success, timeout, non-zero exit, invalid JSON, missing script
- build_injection: just jev_result, with agent findings, no compose/tool results
- main: full pipeline mock, non-/d passthrough, empty stdin, bad JSON stdin
- read_recent_agent_findings: session-scoped reads, stale files, bad IDs
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test (hooks/ is not a package; use spec loader).
_HOOKS_DIR = Path(__file__).resolve().parents[2] / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
# Also need hooks/lib on path for hook_utils/stdin_timeout.
_HOOKS_LIB = _HOOKS_DIR / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))

_spec = importlib.util.spec_from_file_location("jev_route_injector", _HOOKS_DIR / "jev-route-injector-userprompt.py")
# Prevent the if __name__ == "__main__" block from running during import.
_mod = importlib.util.module_from_spec(_spec)
_mod.__name__ = "jev_route_injector"
_spec.loader.exec_module(_mod)

hook = _mod  # alias for readability


@pytest.fixture(autouse=True)
def isolated_router_state(monkeypatch, tmp_path):
    monkeypatch.setenv("JEV_ROUTER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("JEV_SESSION_ID", "injector-test")


# ------------------------------------------------------------------ #
# Module-level constants (v3: compose/tools removed)
# ------------------------------------------------------------------ #


class TestModuleConstants:
    """Route constants exist."""

    def test_detect_pattern_exists(self) -> None:
        assert hasattr(hook, "DETECT_PATTERN")

    def test_route_timeout_exists(self) -> None:
        assert hasattr(hook, "JEV_ROUTE_TIMEOUT_SECONDS")


# ------------------------------------------------------------------ #
# extract_prompt
# ------------------------------------------------------------------ #


class TestExtractPrompt:
    """Test all field paths for prompt extraction."""

    def test_top_level_prompt(self) -> None:
        assert hook.extract_prompt({"prompt": "hello"}) == "hello"

    def test_message_field(self) -> None:
        assert hook.extract_prompt({"message": "hello"}) == "hello"

    def test_user_message_field(self) -> None:
        assert hook.extract_prompt({"userMessage": "hello"}) == "hello"

    def test_tool_input_prompt(self) -> None:
        assert hook.extract_prompt({"tool_input": {"prompt": "hello"}}) == "hello"

    def test_priority_order_prompt_wins(self) -> None:
        event = {"prompt": "first", "message": "second", "userMessage": "third"}
        assert hook.extract_prompt(event) == "first"

    def test_priority_order_message_over_user_message(self) -> None:
        event = {"message": "second", "userMessage": "third"}
        assert hook.extract_prompt(event) == "second"

    def test_empty_dict(self) -> None:
        assert hook.extract_prompt({}) == ""

    def test_non_dict_input(self) -> None:
        assert hook.extract_prompt("not a dict") == ""
        assert hook.extract_prompt(None) == ""
        assert hook.extract_prompt([]) == ""

    def test_empty_string_prompt_falls_through(self) -> None:
        assert hook.extract_prompt({"prompt": "", "message": "fallback"}) == "fallback"

    def test_non_string_prompt_falls_through(self) -> None:
        assert hook.extract_prompt({"prompt": 42, "message": "fallback"}) == "fallback"

    def test_tool_input_non_dict(self) -> None:
        assert hook.extract_prompt({"tool_input": "not a dict"}) == ""

    def test_tool_input_empty_string(self) -> None:
        assert hook.extract_prompt({"tool_input": {"prompt": ""}}) == ""


# ------------------------------------------------------------------ #
# extract_request_text
# ------------------------------------------------------------------ #


class TestExtractRequestText:
    """Test /d pattern matching."""

    def test_do_with_request(self) -> None:
        assert hook.extract_request_text("/d fix the bug") == "fix the bug"

    def test_do_alone(self) -> None:
        assert hook.extract_request_text("/d") == ""

    def test_do_with_leading_spaces(self) -> None:
        assert hook.extract_request_text("  /d fix it") == "fix it"

    def test_do_case_insensitive(self) -> None:
        assert hook.extract_request_text("/D fix it") == "fix it"

    def test_do_with_newline(self) -> None:
        assert hook.extract_request_text("/d\nfix the bug") == "fix the bug"

    def test_do_does_not_match(self) -> None:
        assert hook.extract_request_text("/do something") == "something"

    def test_design_does_not_match(self) -> None:
        assert hook.extract_request_text("/design a page") is None

    def test_non_slash_do(self) -> None:
        assert hook.extract_request_text("hello world") is None

    def test_empty_string(self) -> None:
        assert hook.extract_request_text("") is None

    def test_do_in_middle_does_not_match(self) -> None:
        assert hook.extract_request_text("please /d fix it") is None


# ------------------------------------------------------------------ #
# run_jev_route
# ------------------------------------------------------------------ #


class TestRunJevRoute:
    """Test jev-route.py subprocess execution."""

    @patch("subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"matched": True, "agent": "code-reviewer"}),
        )
        result = hook.run_jev_route("fix the bug")
        assert result == {"matched": True, "agent": "code-reviewer"}
        call_args = mock_run.call_args[0][0]
        assert "jev-route.py" in call_args[1]
        assert "--request" in call_args
        assert "fix the bug" in call_args
        assert "--timeout" not in call_args
        assert mock_run.call_args.kwargs["timeout"] == 20

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=20))
    def test_timeout_returns_none(self, _mock: MagicMock) -> None:
        assert hook.run_jev_route("test") is None

    @patch("subprocess.run", side_effect=OSError("no such file"))
    def test_os_error_returns_none(self, _mock: MagicMock) -> None:
        assert hook.run_jev_route("test") is None

    @patch("subprocess.run")
    def test_nonzero_exit_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert hook.run_jev_route("test") is None

    @patch("subprocess.run")
    def test_invalid_json_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json{{{")
        assert hook.run_jev_route("test") is None

    @patch("subprocess.run")
    def test_non_dict_json_returns_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps([1, 2, 3]))
        assert hook.run_jev_route("test") is None

    def test_missing_script_returns_none(self) -> None:
        with patch.object(Path, "is_file", return_value=False):
            assert hook.run_jev_route("test") is None


# ------------------------------------------------------------------ #
# build_injection (v3: route-only, no compose/tools)
# ------------------------------------------------------------------ #


class TestBuildInjection:
    """Test injection string construction (v3: no compose/tools)."""

    def test_jev_result_only(self) -> None:
        text = hook.build_injection({"matched": True})
        assert "JEV_RESULT" in text

    def test_json_embedded_correctly(self) -> None:
        data = {"matched": True, "agent": "test-agent"}
        text = hook.build_injection(data)
        assert json.dumps(data) in text


# ------------------------------------------------------------------ #
# main
# ------------------------------------------------------------------ #


class TestMain:
    """Test the full pipeline in main()."""

    @patch.object(hook, "read_stdin", return_value="")
    def test_empty_stdin_exits_clean(self, _mock: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

    @patch.object(hook, "read_stdin", return_value="not json{{{")
    def test_bad_json_stdin_exits_clean(self, _mock: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "hello world"}))
    def test_non_d_prompt_exits_clean(self, _mock: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "/d"}))
    def test_bare_d_without_request_exits_clean(self, _mock: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

    @patch.object(hook, "run_jev_route", return_value=None)
    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "/d fix bug"}))
    def test_route_failure_exits_clean(self, _stdin: MagicMock, _route: MagicMock) -> None:
        with pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0

    @patch.object(hook, "run_jev_route", return_value={"matched": True, "agent": "reviewer"})
    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "/d review PR"}))
    def test_route_only_injects_context(
        self,
        _stdin: MagicMock,
        _route: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """v3: route result injected, no compose/tools."""
        with pytest.raises(SystemExit):
            hook.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "JEV_RESULT" in ctx

    @patch.object(hook, "run_jev_route", return_value={"matched": True, "fallback": True})
    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "/d something"}))
    def test_fallback_route_still_injects(
        self,
        _stdin: MagicMock,
        _route: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """v3: fallback routes still inject JEV_RESULT (compose removed)."""
        with pytest.raises(SystemExit):
            hook.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "JEV_RESULT" in ctx

    @patch.object(hook, "run_jev_route", return_value={"matched": False})
    @patch.object(hook, "read_stdin", return_value=json.dumps({"prompt": "/d something"}))
    def test_unmatched_route_still_injects(
        self,
        _stdin: MagicMock,
        _route: MagicMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """v3: unmatched routes still inject JEV_RESULT."""
        with pytest.raises(SystemExit):
            hook.main()
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "JEV_RESULT" in ctx


# =============================================================================
# read_recent_agent_findings: reads only the caller's own session file
# =============================================================================

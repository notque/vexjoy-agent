"""Tests for hooks/posttool-auto-test.py.

Tests the logic (file detection, debounce, language mapping, output formatting)
without actually running test commands — subprocess.run is mocked throughout.

Run with: python -m pytest scripts/tests/test_auto_test_hook.py -v
"""

import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Import hook module (hyphenated filename) ─────────────────────

HOOK_PATH = Path(__file__).resolve().parent.parent.parent / "hooks" / "posttool-auto-test.py"
spec = importlib.util.spec_from_file_location("posttool_auto_test", HOOK_PATH)
hook_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_mod)

_mod = "posttool_auto_test"


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_debounce(tmp_path, monkeypatch):
    """Redirect debounce file to tmp_path and ensure clean state."""
    debounce = tmp_path / "auto-test-last-run"
    monkeypatch.setattr(hook_mod, "_DEBOUNCE_FILE", debounce)
    return debounce


def _make_event(file_path: str) -> str:
    """Build a minimal PostToolUse event JSON string."""
    return json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path},
        }
    )


# ── Extension detection ──────────────────────────────────────────


class TestShouldSkipExtension:
    def test_skip_markdown(self):
        assert hook_mod._should_skip_extension("docs/README.md") is True

    def test_skip_json(self):
        assert hook_mod._should_skip_extension("config.json") is True

    def test_skip_yaml(self):
        assert hook_mod._should_skip_extension("deploy.yaml") is True

    def test_skip_toml(self):
        assert hook_mod._should_skip_extension("pyproject.toml") is True

    def test_skip_no_extension(self):
        assert hook_mod._should_skip_extension("Makefile") is True

    def test_allow_python(self):
        assert hook_mod._should_skip_extension("app.py") is False

    def test_allow_go(self):
        assert hook_mod._should_skip_extension("main.go") is False


# ── Language mapping ─────────────────────────────────────────────


class TestGetTestCommand:
    def test_python_with_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        cmd = hook_mod._get_test_command("src/app.py")
        assert cmd is not None
        assert "ruff check" in cmd
        assert "--config pyproject.toml" in cmd
        assert "pytest" in cmd

    def test_python_without_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd = hook_mod._get_test_command("src/app.py")
        assert cmd is not None
        assert "--config pyproject.toml" not in cmd
        assert "pytest" in cmd

    def test_go_file(self):
        cmd = hook_mod._get_test_command("pkg/server/handler.go")
        assert cmd is not None
        assert "go test" in cmd
        assert "pkg/server" in cmd

    def test_unknown_extension_returns_none(self):
        assert hook_mod._get_test_command("lib.rs") is None

    def test_typescript_returns_none(self):
        assert hook_mod._get_test_command("app.ts") is None


# ── Debounce ─────────────────────────────────────────────────────


class TestDebounce:
    def test_no_debounce_file(self):
        assert hook_mod._is_debounced() is False

    def test_recent_run_is_debounced(self, _clean_debounce):
        _clean_debounce.write_text(str(time.time()))
        assert hook_mod._is_debounced() is True

    def test_old_run_not_debounced(self, _clean_debounce):
        _clean_debounce.write_text(str(time.time() - 20))
        assert hook_mod._is_debounced() is False

    def test_update_debounce_writes_file(self, _clean_debounce):
        hook_mod._update_debounce()
        assert _clean_debounce.exists()
        ts = float(_clean_debounce.read_text())
        assert time.time() - ts < 2


# ── Test execution ───────────────────────────────────────────────


class TestRunTests:
    @patch.object(hook_mod.subprocess, "run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="3 passed\n", stderr="")
        success, output = hook_mod._run_tests("pytest")
        assert success is True
        assert "3 passed" in output

    @patch.object(hook_mod.subprocess, "run")
    def test_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="FAILED test_foo\n", stderr="")
        success, output = hook_mod._run_tests("pytest")
        assert success is False
        assert "FAILED" in output

    @patch.object(hook_mod.subprocess, "run")
    def test_timeout(self, mock_run):
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("pytest", 30)
        success, output = hook_mod._run_tests("pytest")
        assert success is False
        assert "timed out" in output.lower()

    @patch.object(hook_mod.subprocess, "run")
    def test_output_truncation(self, mock_run):
        long_output = "\n".join(f"line {i}" for i in range(50))
        mock_run.return_value = MagicMock(returncode=0, stdout=long_output, stderr="")
        _, output = hook_mod._run_tests("pytest")
        assert len(output.splitlines()) <= 20


# ── Output formatting ────────────────────────────────────────────


class TestFormatResult:
    def test_pass_format(self):
        result = hook_mod._format_result("src/app.py", True, "3 passed")
        assert "additionalContext" in result
        assert "PASS" in result["additionalContext"]
        assert "app.py" in result["additionalContext"]

    def test_fail_format(self):
        result = hook_mod._format_result("src/app.py", False, "FAILED test_foo")
        assert "FAIL" in result["additionalContext"]


# ── End-to-end main() ───────────────────────────────────────────


class TestMain:
    @patch.object(hook_mod, "_run_tests", return_value=(True, "3 passed"))
    @patch.object(hook_mod, "_get_test_command", return_value="pytest")
    @patch.object(hook_mod, "read_stdin")
    def test_python_file_runs_tests(self, mock_stdin, mock_cmd, mock_run, capsys):
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        mock_run.assert_called_once()
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "PASS" in result["additionalContext"]

    @patch.object(hook_mod, "read_stdin")
    def test_markdown_file_skipped(self, mock_stdin, capsys):
        mock_stdin.return_value = _make_event("README.md")
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "_run_tests", return_value=(True, "ok"))
    @patch.object(hook_mod, "_get_test_command", return_value="go test ./...")
    @patch.object(hook_mod, "read_stdin")
    def test_go_file_runs_tests(self, mock_stdin, mock_cmd, mock_run, capsys):
        mock_stdin.return_value = _make_event("pkg/handler.go")
        hook_mod.main()
        mock_run.assert_called_once()

    @patch.object(hook_mod, "read_stdin")
    def test_unknown_extension_skipped(self, mock_stdin, capsys):
        mock_stdin.return_value = _make_event("lib.rs")
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "read_stdin")
    def test_debounce_skips_second_call(self, mock_stdin, capsys):
        """Second call within debounce window is skipped."""
        hook_mod._update_debounce()
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "_run_tests", return_value=(True, "ok"))
    @patch.object(hook_mod, "_get_test_command", return_value="pytest")
    @patch.object(hook_mod, "read_stdin")
    def test_debounce_allows_after_window(self, mock_stdin, mock_cmd, mock_run, _clean_debounce, capsys):
        """Call after debounce window runs tests."""
        _clean_debounce.write_text(str(time.time() - 20))
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        mock_run.assert_called_once()

    @patch.object(hook_mod, "read_stdin")
    def test_malformed_stdin_exits_cleanly(self, mock_stdin, capsys):
        mock_stdin.return_value = "not json at all {"
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "read_stdin")
    def test_empty_stdin_exits_cleanly(self, mock_stdin, capsys):
        mock_stdin.return_value = ""
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "_run_tests", return_value=(False, "Tests timed out (>30s), skipping auto-test"))
    @patch.object(hook_mod, "_get_test_command", return_value="pytest")
    @patch.object(hook_mod, "read_stdin")
    def test_timeout_returns_message(self, mock_stdin, mock_cmd, mock_run, capsys):
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "timed out" in result["additionalContext"].lower()

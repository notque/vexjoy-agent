"""Tests for hooks/posttool-auto-test.py.

Tests the logic (file detection, debounce, language mapping, output formatting,
output sanitization, shell safety) without actually running test commands —
subprocess.Popen is mocked throughout.

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
    """Redirect debounce file and lock to tmp_path and ensure clean state."""
    debounce = tmp_path / "auto-test-last-run"
    lock = tmp_path / "auto-test-last-run.lock"
    monkeypatch.setattr(hook_mod, "_DEBOUNCE_FILE", debounce)
    monkeypatch.setattr(hook_mod, "_DEBOUNCE_LOCK", lock)
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
        cmds = hook_mod._get_test_command("src/app.py")
        assert cmds is not None
        assert len(cmds) == 2
        # First command is ruff
        assert "ruff" in cmds[0]
        assert "--config" in cmds[0]
        assert "pyproject.toml" in cmds[0]
        # Second command is pytest
        assert "pytest" in cmds[1]

    def test_python_without_pyproject(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmds = hook_mod._get_test_command("src/app.py")
        assert cmds is not None
        assert len(cmds) == 2
        assert "--config" not in cmds[0]
        assert "pytest" in cmds[1]

    def test_go_file(self):
        cmds = hook_mod._get_test_command("pkg/server/handler.go")
        assert cmds is not None
        assert len(cmds) == 1
        assert "go" in cmds[0]
        assert "test" in cmds[0]
        assert "pkg/server" in cmds[0][2]

    def test_unknown_extension_returns_none(self):
        assert hook_mod._get_test_command("lib.rs") is None

    def test_typescript_returns_none(self):
        assert hook_mod._get_test_command("app.ts") is None

    def test_returns_list_args_not_shell_string(self, tmp_path, monkeypatch):
        """Commands are lists (shell=False safe), not shell strings."""
        monkeypatch.chdir(tmp_path)
        cmds = hook_mod._get_test_command("src/app.py")
        assert cmds is not None
        for cmd in cmds:
            assert isinstance(cmd, list)
            for arg in cmd:
                assert isinstance(arg, str)

    def test_file_path_with_spaces_in_args(self, tmp_path, monkeypatch):
        """File paths with shell metacharacters are passed as single list elements."""
        monkeypatch.chdir(tmp_path)
        tricky_path = "src/my file; rm -rf.py"
        cmds = hook_mod._get_test_command(tricky_path)
        assert cmds is not None
        # The file path must appear as a single element, not split by shell
        ruff_cmd = cmds[0]
        assert tricky_path in ruff_cmd


# ── Debounce ─────────────────────────────────────────────────────


class TestDebounce:
    def test_no_debounce_file_proceeds(self):
        assert hook_mod._debounce_check_and_update() is True

    def test_recent_run_is_debounced(self, _clean_debounce):
        _clean_debounce.write_text(str(time.time()))
        assert hook_mod._debounce_check_and_update() is False

    def test_old_run_not_debounced(self, _clean_debounce):
        _clean_debounce.write_text(str(time.time() - 20))
        assert hook_mod._debounce_check_and_update() is True

    def test_atomic_update_writes_file(self, _clean_debounce):
        hook_mod._debounce_check_and_update()
        assert _clean_debounce.exists()
        ts = float(_clean_debounce.read_text())
        assert time.time() - ts < 2

    def test_second_call_within_window_blocked(self, _clean_debounce):
        """First call proceeds, second within window is blocked."""
        assert hook_mod._debounce_check_and_update() is True
        assert hook_mod._debounce_check_and_update() is False


# ── Output sanitization ─────────────────────────────────────────


class TestSanitizeOutput:
    def test_normal_output_unchanged(self):
        text = "3 passed in 0.5s\nFAILED test_foo"
        assert hook_mod._sanitize_output(text) == text

    def test_redacts_password(self):
        text = "loading config\nDATABASE_PASSWORD=hunter2\nstarting"
        result = hook_mod._sanitize_output(text)
        assert "hunter2" not in result
        assert "DATABASE_PASSWORD=<REDACTED>" in result

    def test_redacts_api_key(self):
        text = "ANTHROPIC_API_KEY=sk-ant-1234\nOPENAI_API_KEY=sk-5678"
        result = hook_mod._sanitize_output(text)
        assert "sk-ant-1234" not in result
        assert "sk-5678" not in result
        assert "ANTHROPIC_API_KEY=<REDACTED>" in result
        assert "OPENAI_API_KEY=<REDACTED>" in result

    def test_redacts_aws_keys(self):
        text = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI\nAWS_ACCESS_KEY_ID=AKIAIOSFODNN"
        result = hook_mod._sanitize_output(text)
        assert "wJalrXUtnFEMI" not in result
        assert "AKIAIOSFODNN" not in result

    def test_redacts_token(self):
        text = "AUTH_TOKEN=abc123secret"
        result = hook_mod._sanitize_output(text)
        assert "abc123secret" not in result
        assert "AUTH_TOKEN=<REDACTED>" in result

    def test_non_secret_caps_key_preserved(self):
        """ALL_CAPS=value lines without secret keywords are kept."""
        text = "PYTHONPATH=/usr/local/lib\nPATH=/usr/bin"
        result = hook_mod._sanitize_output(text)
        assert result == text

    def test_lowercase_lines_preserved(self):
        """Regular test output lines are not stripped."""
        text = "test_foo.py::test_bar PASSED\npassword=foo in test fixture"
        result = hook_mod._sanitize_output(text)
        assert result == text

    def test_redacts_database_url(self):
        text = "DATABASE_URL=postgres://user:pass@host/db"
        result = hook_mod._sanitize_output(text)
        assert "postgres://user:pass@host/db" not in result
        assert "DATABASE_URL=<REDACTED>" in result


# ── Test execution ───────────────────────────────────────────────


class TestRunTests:
    @patch.object(hook_mod.subprocess, "Popen")
    def test_success(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = ("3 passed\n", None)
        proc.returncode = 0
        mock_popen.return_value = proc
        success, output = hook_mod._run_tests([["pytest"]])
        assert success is True
        assert "3 passed" in output

    @patch.object(hook_mod.subprocess, "Popen")
    def test_failure(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = ("FAILED test_foo\n", None)
        proc.returncode = 1
        mock_popen.return_value = proc
        success, output = hook_mod._run_tests([["pytest"]])
        assert success is False
        assert "FAILED" in output

    @patch("os.killpg")
    @patch.object(hook_mod.subprocess, "Popen")
    def test_timeout_kills_process_group(self, mock_popen, mock_killpg):
        from subprocess import TimeoutExpired

        proc = MagicMock()
        proc.pid = 12345
        proc.communicate.side_effect = TimeoutExpired("pytest", 15)
        proc.wait.return_value = None
        mock_popen.return_value = proc
        success, output = hook_mod._run_tests([["pytest"]])
        assert success is False
        assert "timed out" in output.lower()
        # Verify process group was killed
        mock_killpg.assert_called_once_with(12345, hook_mod.signal.SIGTERM)

    @patch.object(hook_mod.subprocess, "Popen")
    def test_output_truncation(self, mock_popen):
        long_output = "\n".join(f"line {i}" for i in range(50))
        proc = MagicMock()
        proc.communicate.return_value = (long_output, None)
        proc.returncode = 0
        mock_popen.return_value = proc
        _, output = hook_mod._run_tests([["pytest"]])
        assert len(output.splitlines()) <= 20

    @patch.object(hook_mod.subprocess, "Popen")
    def test_multiple_commands_all_pass(self, mock_popen):
        proc = MagicMock()
        proc.communicate.return_value = ("ok\n", None)
        proc.returncode = 0
        mock_popen.return_value = proc
        success, _ = hook_mod._run_tests([["ruff", "check"], ["pytest"]])
        assert success is True
        assert mock_popen.call_count == 2

    @patch.object(hook_mod.subprocess, "Popen")
    def test_multiple_commands_one_fails(self, mock_popen):
        pass_proc = MagicMock()
        pass_proc.communicate.return_value = ("ok\n", None)
        pass_proc.returncode = 0
        fail_proc = MagicMock()
        fail_proc.communicate.return_value = ("FAIL\n", None)
        fail_proc.returncode = 1
        mock_popen.side_effect = [pass_proc, fail_proc]
        success, _ = hook_mod._run_tests([["ruff", "check"], ["pytest"]])
        assert success is False

    @patch.object(hook_mod.subprocess, "Popen")
    def test_output_sanitized(self, mock_popen):
        """Secrets in test output are redacted before returning."""
        proc = MagicMock()
        proc.communicate.return_value = ("ok\nANTHROPIC_API_KEY=sk-secret-123\ndone\n", None)
        proc.returncode = 0
        mock_popen.return_value = proc
        _, output = hook_mod._run_tests([["pytest"]])
        assert "sk-secret-123" not in output
        assert "ANTHROPIC_API_KEY=<REDACTED>" in output

    @patch.object(hook_mod.subprocess, "Popen")
    def test_popen_uses_shell_false(self, mock_popen):
        """Popen is called without shell=True (list args, no shell)."""
        proc = MagicMock()
        proc.communicate.return_value = ("ok\n", None)
        proc.returncode = 0
        mock_popen.return_value = proc
        hook_mod._run_tests([["pytest", "-v"]])
        call_kwargs = mock_popen.call_args
        # shell should not be in kwargs, or should be False
        assert call_kwargs.kwargs.get("shell", False) is False
        # First positional arg should be the list
        assert call_kwargs.args[0] == ["pytest", "-v"]

    @patch.object(hook_mod.subprocess, "Popen")
    def test_popen_starts_new_session(self, mock_popen):
        """Popen is called with start_new_session=True for process group cleanup."""
        proc = MagicMock()
        proc.communicate.return_value = ("ok\n", None)
        proc.returncode = 0
        mock_popen.return_value = proc
        hook_mod._run_tests([["pytest"]])
        assert mock_popen.call_args.kwargs.get("start_new_session") is True


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
    @patch.object(hook_mod, "_get_test_command", return_value=[["pytest"]])
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
    @patch.object(hook_mod, "_get_test_command", return_value=[["go", "test", "./..."]])
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

    @patch.object(hook_mod, "_run_tests", return_value=(True, "ok"))
    @patch.object(hook_mod, "_get_test_command", return_value=[["pytest"]])
    @patch.object(hook_mod, "read_stdin")
    def test_debounce_skips_second_call(self, mock_stdin, mock_cmd, mock_run, capsys):
        """First call proceeds; second within debounce window is skipped."""
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        assert capsys.readouterr().out != ""
        # Second call within debounce window
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        assert capsys.readouterr().out == ""

    @patch.object(hook_mod, "_run_tests", return_value=(True, "ok"))
    @patch.object(hook_mod, "_get_test_command", return_value=[["pytest"]])
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

    @patch.object(hook_mod, "_run_tests", return_value=(False, "Command timed out (>15s)"))
    @patch.object(hook_mod, "_get_test_command", return_value=[["pytest"]])
    @patch.object(hook_mod, "read_stdin")
    def test_timeout_returns_message(self, mock_stdin, mock_cmd, mock_run, capsys):
        mock_stdin.return_value = _make_event("src/app.py")
        hook_mod.main()
        out = capsys.readouterr().out
        result = json.loads(out)
        assert "timed out" in result["additionalContext"].lower()

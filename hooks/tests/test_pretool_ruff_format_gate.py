#!/usr/bin/env python3
"""
Tests for the pretool-ruff-format-gate hook.

Run with: python3 -m pytest hooks/tests/test_pretool_ruff_format_gate.py -v
"""

import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-ruff-format-gate.py"

spec = importlib.util.spec_from_file_location("pretool_ruff_format_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bash_event(command: str, cwd: str | None = None) -> str:
    event = {"tool_input": {"command": command}}
    if cwd:
        event["cwd"] = cwd
    return json.dumps(event)


def _run_main(stdin_payload: str, env: dict | None = None) -> tuple[int, dict | None]:
    """Invoke mod.main() in-process.

    Returns (logical_exit_code, parsed_stdout_json).
    logical_exit_code is 2 if permissionDecision:deny was emitted, 0 otherwise.
    """
    base_env = dict(os.environ)
    base_env.pop("RUFF_FORMAT_GATE_BYPASS", None)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    parsed = None
    if output:
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            pass

    if parsed:
        hook_out = parsed.get("hookSpecificOutput", {})
        if hook_out.get("permissionDecision") == "deny":
            return 2, parsed
    return 0, parsed


# ---------------------------------------------------------------------------
# Non-push commands pass through
# ---------------------------------------------------------------------------


class TestNonPushCommandsPassThrough:
    def test_git_status_allowed(self):
        code, _ = _run_main(_make_bash_event("git status"))
        assert code == 0

    def test_git_commit_allowed(self):
        code, _ = _run_main(_make_bash_event("git commit -m 'feat: something'"))
        assert code == 0

    def test_git_fetch_allowed(self):
        code, _ = _run_main(_make_bash_event("git fetch origin"))
        assert code == 0

    def test_empty_command_allowed(self):
        code, _ = _run_main(_make_bash_event(""))
        assert code == 0

    def test_non_git_command_allowed(self):
        code, _ = _run_main(_make_bash_event("echo 'hello'"))
        assert code == 0


# ---------------------------------------------------------------------------
# No pyproject.toml — pass through
# ---------------------------------------------------------------------------


class TestNoRuffConfig:
    def test_no_pyproject_passes_through(self, tmp_path):
        """No pyproject.toml means the gate is dormant (non-Python project)."""
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload)
        assert code == 0

    def test_pyproject_without_ruff_section_passes_through(self, tmp_path):
        """pyproject.toml without [tool.ruff] is treated as non-Python project."""
        (tmp_path / "pyproject.toml").write_text("[build-system]\nrequires = []\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload)
        assert code == 0


# ---------------------------------------------------------------------------
# Bypass env var
# ---------------------------------------------------------------------------


class TestBypassEnv:
    def test_bypass_allows_push_through(self, tmp_path):
        """RUFF_FORMAT_GATE_BYPASS=1 skips the check entirely."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))
        code, _ = _run_main(payload, env={"RUFF_FORMAT_GATE_BYPASS": "1"})
        assert code == 0


# ---------------------------------------------------------------------------
# Ruff check outcomes
# ---------------------------------------------------------------------------


class TestRuffCheckOutcomes:
    def test_ruff_check_passes_allows_push(self, tmp_path):
        """When ruff format --check exits 0, the push is allowed."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            code, _ = _run_main(payload)
        assert code == 0

    def test_ruff_check_fails_blocks_push(self, tmp_path):
        """When ruff format --check exits non-zero, the push is blocked."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        mock_result = type("R", (), {"returncode": 1, "stdout": "Would reformat: foo.py\n", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            code, parsed = _run_main(payload)
        assert code == 2
        assert parsed is not None
        hook_out = parsed["hookSpecificOutput"]
        assert hook_out["permissionDecision"] == "deny"
        assert "ruff format" in hook_out["permissionDecisionReason"]

    def test_ruff_not_installed_allows_push(self, tmp_path):
        """FileNotFoundError (ruff not installed) fails open — push allowed."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        with patch("subprocess.run", side_effect=FileNotFoundError("ruff not found")):
            code, _ = _run_main(payload)
        assert code == 0

    def test_ruff_timeout_allows_push(self, tmp_path):
        """Timeout in ruff invocation fails open — push allowed."""
        import subprocess

        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["ruff"], 15)):
            code, _ = _run_main(payload)
        assert code == 0

    def test_deny_reason_includes_ruff_output(self, tmp_path):
        """Ruff violation output is included in the deny reason for visibility."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        payload = _make_bash_event("git push origin main", cwd=str(tmp_path))

        violation_msg = "Would reformat: src/app.py\n1 file would be reformatted"
        mock_result = type("R", (), {"returncode": 1, "stdout": violation_msg, "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            code, parsed = _run_main(payload)
        assert code == 2
        reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
        assert "ruff output" in reason
        assert "src/app.py" in reason


# ---------------------------------------------------------------------------
# CWD extraction
# ---------------------------------------------------------------------------


class TestCwdExtraction:
    def test_cd_prefix_extracts_cwd(self, tmp_path):
        """cd /path && git push correctly uses /path as project root."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        command = f"cd {tmp_path} && git push origin main"
        payload = _make_bash_event(command)

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            code, _ = _run_main(payload)
        assert code == 0
        # Verify ruff was invoked in the extracted directory
        if mock_run.called:
            call_kwargs = mock_run.call_args
            assert str(tmp_path) in str(call_kwargs)

    def test_git_C_flag_extracts_cwd(self, tmp_path):
        """git -C /path push correctly uses /path as project root."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        command = f"git -C {tmp_path} push origin main"
        payload = _make_bash_event(command)

        mock_result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            code, _ = _run_main(payload)
        assert code == 0


# ---------------------------------------------------------------------------
# Fail open on malformed input
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_malformed_json_exits_0(self):
        code, _ = _run_main("not valid json {{{")
        assert code == 0

    def test_empty_stdin_exits_0(self):
        code, _ = _run_main("")
        assert code == 0

    def test_null_json_exits_0(self):
        code, _ = _run_main("null")
        assert code == 0

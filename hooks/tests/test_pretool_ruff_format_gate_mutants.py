#!/usr/bin/env python3
"""Mutation-kill tests for pretool-ruff-format-gate.

Pins what the base suites left open: exit codes on every early-out, the
shell-parsing edge cases of push detection (bare `cd`, bare env assignments,
global git options, unbalanced quotes), the pyproject search depth, fail-open
on ruff/git failures, and when ruff's own output reaches stderr or the denial.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-ruff-format-gate.py"
spec = importlib.util.spec_from_file_location("pretool_ruff_format_gate_mut", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PUSH = "git " + "push"


def _run(payload, capsys, *, debug=False, env=None):
    """Run main() in-process; return (exit_code, deny_reason_or_None, stderr)."""
    base = {k: v for k, v in os.environ.items() if k not in ("RUFF_FORMAT_GATE_BYPASS", "CLAUDE_HOOKS_DEBUG")}
    if debug:
        base["CLAUDE_HOOKS_DEBUG"] = "1"
    base.update(env or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    code = None
    with patch.dict(os.environ, base, clear=True), patch.object(mod, "read_stdin", return_value=raw):
        try:
            mod.main()
        except SystemExit as exc:
            code = exc.code
    out = capsys.readouterr()
    reason = None
    if out.out.strip():
        hook_out = json.loads(out.out)["hookSpecificOutput"]
        if hook_out["permissionDecision"] == "deny":
            reason = hook_out["permissionDecisionReason"]
    return code, reason, out.err


def _push_event(cwd, command=PUSH):
    return {"tool_input": {"command": command}, "cwd": str(cwd)}


@pytest.fixture
def ruff_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
    return tmp_path


def _push_cwds_guarded(command, cwd):
    """Call _push_cwds in a child process so a parser hang fails instead of freezing pytest."""
    code = (
        "import importlib.util, sys, json\n"
        f"s = importlib.util.spec_from_file_location('h', {str(HOOK_PATH)!r})\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "print(json.dumps([str(p) for p in m._push_cwds(sys.argv[1], sys.argv[2])]))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, command, str(cwd)], capture_output=True, text=True, timeout=15, check=False
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


class TestExitCodes:
    def test_malformed_json_exits_zero(self, capsys):
        code, reason, _ = _run("{nope", capsys)
        assert code == 0 and reason is None

    def test_non_object_json_exits_zero(self, capsys):
        code, reason, _ = _run("[1, 2]", capsys)
        assert code == 0 and reason is None

    def test_missing_command_exits_zero(self, capsys):
        code, reason, _ = _run({"tool_input": {}}, capsys)
        assert code == 0 and reason is None

    def test_bypass_exits_zero_and_is_quiet(self, ruff_project, capsys):
        code, reason, err = _run(_push_event(ruff_project), capsys, env={"RUFF_FORMAT_GATE_BYPASS": "1"})
        assert code == 0 and reason is None
        assert err == ""

    def test_bypass_with_debug_says_so(self, ruff_project, capsys):
        _, _, err = _run(_push_event(ruff_project), capsys, debug=True, env={"RUFF_FORMAT_GATE_BYPASS": "1"})
        assert err.strip()

    def test_push_outside_a_ruff_project_is_allowed(self, tmp_path, capsys):
        (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        with patch.object(mod, "_changed_python_files", side_effect=AssertionError("must not be reached")):
            code, reason, err = _run(_push_event(tmp_path), capsys)
        assert code == 0 and reason is None
        assert err == ""


class TestDebugAndOutput:
    def _violation(self, ruff_project, capsys, output, *, debug):
        with (
            patch.object(mod, "_changed_python_files", return_value=[Path("bad.py")]),
            patch.object(mod, "_run_ruff_format_check", return_value=(1, output)),
        ):
            return _run(_push_event(ruff_project), capsys, debug=debug)

    def test_ruff_output_stays_off_stderr_without_debug(self, ruff_project, capsys):
        code, reason, err = self._violation(ruff_project, capsys, "Would reformat: bad.py", debug=False)
        assert code == 0 and reason
        assert "Would reformat" not in err
        assert "Would reformat" in reason

    def test_ruff_output_goes_to_stderr_with_debug(self, ruff_project, capsys):
        _, reason, err = self._violation(ruff_project, capsys, "Would reformat: bad.py", debug=True)
        assert reason
        assert "Would reformat: bad.py" in err

    def test_debug_names_the_project_being_checked(self, ruff_project, capsys):
        _, _, err = self._violation(ruff_project, capsys, "x", debug=True)
        assert str(ruff_project.resolve()) in err

    def test_denial_cuts_output_only_past_300_chars(self, ruff_project, capsys):
        _, at_limit, _ = self._violation(ruff_project, capsys, "a" * 300, debug=False)
        _, over_limit, _ = self._violation(ruff_project, capsys, "a" * 301, debug=False)
        assert at_limit.endswith("a" * 300)
        assert over_limit.endswith("a" * 300 + "...")

    def test_clean_changed_files_allow(self, ruff_project, capsys):
        with (
            patch.object(mod, "_changed_python_files", return_value=[Path("ok.py")]),
            patch.object(mod, "_run_ruff_format_check", return_value=(0, "")),
        ):
            code, reason, _ = _run(_push_event(ruff_project), capsys)
        assert code == 0 and reason is None


class TestRuffRunnerFailsOpen:
    def test_ruff_timeout_does_not_block(self, tmp_path):
        with patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("ruff", 15)):
            assert mod._run_ruff_format_check(tmp_path, [Path("a.py")]) == (0, "")

    def test_ruff_os_error_does_not_block(self, tmp_path):
        with patch.object(mod.subprocess, "run", side_effect=PermissionError("no")):
            assert mod._run_ruff_format_check(tmp_path, [Path("a.py")]) == (0, "")

    def test_git_failure_means_no_changed_files(self, tmp_path):
        assert mod._changed_python_files(tmp_path) == []


class TestProjectRootSearch:
    def test_no_cwd_finds_nothing(self):
        assert mod._find_project_root(None) is None
        assert mod._find_project_root("") is None

    def test_climbs_five_levels_but_not_six(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
        near = tmp_path.joinpath(*"abcde")
        far = tmp_path.joinpath(*"abcdef")
        far.mkdir(parents=True)
        assert mod._find_project_root(str(near)) == tmp_path.resolve()
        assert mod._find_project_root(str(far)) is None


class TestPushParsing:
    def test_unbalanced_quote_is_not_a_push(self, tmp_path):
        assert mod._push_cwds("echo 'oops && " + PUSH, str(tmp_path)) == []

    def test_bare_cd_does_not_crash_or_move(self, tmp_path):
        assert mod._push_cwds("cd; " + PUSH, str(tmp_path)) == [tmp_path.resolve()]

    def test_bare_env_assignment_does_not_crash(self, tmp_path):
        assert mod._push_cwds("FOO=1; " + PUSH, str(tmp_path)) == [tmp_path.resolve()]

    def test_bare_env_command_does_not_crash(self, tmp_path):
        assert mod._push_cwds("env FOO=1; " + PUSH, str(tmp_path)) == [tmp_path.resolve()]

    def test_leading_env_assignment_is_skipped(self, tmp_path):
        assert mod._push_cwds("FOO=1 " + PUSH, str(tmp_path)) == [tmp_path.resolve()]

    def test_relative_cd_without_a_default_cwd_resolves_from_process_cwd(self):
        expected = [Path("sub").resolve()]
        assert mod._push_cwds("cd sub && " + PUSH, None) == expected
        assert mod._push_cwds("cd sub && " + PUSH, "") == expected

    def test_relative_git_C_without_a_default_cwd(self):
        assert mod._push_cwds("git -C sub push", None) == [Path("sub").resolve()]

    def test_cd_then_push_with_default_cwd(self, tmp_path):
        assert mod._push_cwds("cd sub && " + PUSH, str(tmp_path)) == [(tmp_path / "sub").resolve()]

    @pytest.mark.parametrize(
        "command",
        [
            "git --no-pager push",
            "git --git-dir=.git push",
            "git --bare -c a.b=c push origin main",
            "git -p push",
        ],
    )
    def test_global_git_flags_before_push_still_find_the_push(self, tmp_path, command):
        assert _push_cwds_guarded(command, tmp_path) == [str(tmp_path.resolve())]

    @pytest.mark.parametrize(
        "command",
        [
            "cd /tmp/some-dir/inner && " + PUSH + " origin feature/x:refs/heads/x",
            "git -C /tmp/some-dir/inner push --force-with-lease=main:abc123",
            "git push origin ~/branch",
        ],
    )
    def test_paths_and_refspecs_are_not_split_into_fragments(self, tmp_path, command):
        result = mod._push_cwds(command, str(tmp_path))
        assert len(result) == 1
        if "some-dir" in command:
            assert result == [Path("/tmp/some-dir/inner").resolve()]

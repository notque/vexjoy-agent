#!/usr/bin/env python3
"""Mutation-kill tests for pretool-unified-gate.

Each test is a scenario the earlier suites never reached: git aliases with
trailing args, escaped separators, `eval` chains, `--bind=` loopback, JSON-only
python sinks, advisory (warn-only) patterns, comment stripping, guard-integrity
scope, `.guard-patterns` parsing, and worktree push exemptions.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate_mutants.py -v
"""

import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-unified-gate.py"

spec = importlib.util.spec_from_file_location("pretool_unified_gate_mutants", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PUSH = "git " + "push"
FIREWALL_OFF = "ufw " + "disable"


def _run(command: str, *, env: dict | None = None):
    """Run main() in-process on a Bash call. Returns (denied, reason, stderr)."""
    base = {k: v for k, v in os.environ.items() if not k.endswith("_BYPASS")}
    base["CLAUDE_OPERATOR_PROFILE"] = "work"
    base.update(env or {})
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    out, err = io.StringIO(), io.StringIO()
    with (
        patch.dict(os.environ, base, clear=True),
        patch.object(mod, "read_stdin", return_value=payload),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
    ):
        try:
            mod.main()
        except SystemExit:
            pass
    text = out.getvalue().strip()
    if not text:
        return False, "", err.getvalue()
    decision = json.loads(text)["hookSpecificOutput"]
    return decision["permissionDecision"] == "deny", decision["permissionDecisionReason"], err.getvalue()


def _denied(command: str, **kw) -> bool:
    return _run(command, **kw)[0]


def _blocked_by(fn, *args):
    """Call a check function that ends in _block(); return True if it denied."""
    out = io.StringIO()
    with patch("sys.stdout", out), patch("sys.stderr", io.StringIO()):
        try:
            fn(*args)
        except SystemExit:
            pass
    return "deny" in out.getvalue()


# --- git alias / destructive-op parsing -------------------------------------


def test_inline_alias_with_trailing_args_still_expands_to_the_destructive_op():
    assert _denied("git -c alias.zap=reset zap --hard") is True


def test_inline_alias_without_trailing_args_is_not_destructive():
    assert _denied("git -c alias.zap=status zap") is False


def test_explicit_cwd_wins_over_the_event_cwd_for_alias_lookup():
    seen = []

    def fake_run(argv, **kwargs):
        seen.append(kwargs.get("cwd"))
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    with (
        patch.object(mod, "_CURRENT_EVENT", {"cwd": "/event/cwd"}),
        patch.object(mod.subprocess, "run", side_effect=fake_run),
    ):
        mod._destructive_git_operation("git zap", cwd="/explicit/cwd")
    assert seen
    assert set(seen) == {"/explicit/cwd"}


def test_persistent_alias_lookup_is_cached_per_directory():
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="!git reset --hard\n", stderr="")

    cache = {}
    with patch.object(mod.subprocess, "run", side_effect=fake_run):
        first = mod._persistent_git_alias_payload("zap", "/some/dir", cache)
        second = mod._persistent_git_alias_payload("zap", "/some/dir", cache)
    assert first == second == "git reset --hard"
    assert len(calls) == 1


def test_escaped_separator_does_not_split_a_segment():
    assert mod._split_executed_shell_segments("echo a\\;b; ls") == ["echo a\\;b", "ls"]


def test_eval_payload_is_everything_after_the_last_eval():
    assert mod._eval_payload("eval echo eval git status") == "git status"


# --- git push exemption for feature-branch worktrees -------------------------


def test_push_without_a_cd_is_denied_even_if_cwd_is_on_a_feature_branch():
    with patch.object(mod, "_is_worktree_on_feature_branch", return_value=True):
        assert _denied(PUSH + " origin HEAD") is True


def test_push_from_the_project_dir_itself_is_denied_on_a_feature_branch():
    with patch.object(mod, "_is_worktree_on_feature_branch", return_value=True):
        assert _denied(PUSH + " && git -C /proj log", env={"CLAUDE_PROJECT_DIR": "/proj"}) is True


def test_push_from_another_feature_branch_worktree_is_allowed():
    with patch.object(mod, "_is_worktree_on_feature_branch", return_value=True):
        assert _denied(PUSH + " && git -C /tmp/other-wt log", env={"CLAUDE_PROJECT_DIR": "/proj"}) is False


def test_semicolon_cd_prefix_sets_the_effective_dir():
    assert mod._extract_effective_cwd("cd /tmp/x ; git status") == "/tmp/x"
    assert mod._extract_effective_cwd("cd /tmp/x; git status") == "/tmp/x"


# --- public dev server guard --------------------------------------------------


def test_http_server_with_loopback_bind_equals_form_is_allowed():
    assert _denied("python3 -m http.server 8000 --bind=127.0.0.1") is False


def test_http_server_with_wildcard_bind_equals_form_is_denied():
    assert _denied("python3 -m http.server 8000 --bind=0.0.0.0") is True


@pytest.mark.parametrize("reader", ["head", "tail", "cat"])
def test_reader_commands_quoting_a_server_string_are_data(reader):
    assert _denied(f"{reader} -n 3 notes.txt 'python3 -m http.server'") is False


def test_head_showing_a_footgun_string_is_data():
    assert _denied("head -n 3 " + FIREWALL_OFF) is False


def test_unquoted_shell_op_after_a_closed_single_quote_is_seen():
    assert mod._has_unquoted_shell_op("echo 'a' | cat") is True
    assert mod._has_unquoted_shell_op("echo 'a | b'") is False


# --- curl | python sink -------------------------------------------------------

JSON_ONLY = "import json, sys\nprint(json.load(sys.stdin))"


def _pipe_py(code: str) -> str:
    return "curl -s https://example.test/a.json | python3 -c '" + code + "'"


def test_json_only_python_sink_is_allowed():
    assert _denied(_pipe_py(JSON_ONLY)) is False


def test_python_sink_importing_os_is_denied():
    assert _denied(_pipe_py("import os, json, sys\njson.load(sys.stdin)")) is True


def test_python_sink_with_an_aliased_import_is_denied():
    assert _denied(_pipe_py("import json as j, sys\nj.load(sys.stdin)")) is True


def test_python_code_importing_a_non_data_module_does_not_parse_stdin():
    assert mod._py_code_only_parses_stdin("import os, json, sys\njson.load(sys.stdin)") is False


def test_python_sink_that_only_dumps_does_not_count_as_parsing_stdin():
    assert mod._py_code_only_parses_stdin("import json\njson.dumps({})") is False


def test_python_sink_touching_a_non_allowed_sys_attr_is_denied():
    assert mod._py_code_only_parses_stdin("import json, sys\njson.load(sys.stdin)\nsys.modules") is False
    assert mod._py_code_only_parses_stdin("import json, sys\njson.load(sys.stdin)") is True


def test_json_tool_sink_is_allowed_and_other_modules_are_not():
    assert mod._is_data_only_python_sink("python3 -m json.tool") is True
    assert mod._is_data_only_python_sink("python3 -m http.server") is False


def test_second_line_json_sink_is_still_recognised():
    assert _denied("echo start\ncurl -s https://example.test/a | python3 -m json.tool") is False


# --- sysadmin guard -----------------------------------------------------------


def test_footgun_inside_backticks_under_a_display_command_is_denied():
    assert _denied("echo `" + FIREWALL_OFF + "`") is True


def test_footgun_inside_dollar_parens_under_a_display_command_is_denied():
    assert _denied("echo $(" + FIREWALL_OFF + ")") is True


def test_mongod_bind_ip_wildcard_warns_without_denying():
    denied, _, err = _run("mongod --bind_ip 0.0.0.0")
    assert denied is False
    assert "ADVISORY" in err


def test_disabling_known_hosts_file_warns_without_denying():
    denied, _, err = _run("ssh -o UserKnownHostsFile=/dev/null host")
    assert denied is False
    assert "ADVISORY" in err


def test_comment_stripping_honors_an_escaped_quote():
    assert mod._strip_unquoted_comment("echo \\' # " + FIREWALL_OFF).rstrip() == "echo \\'"


def test_git_secret_check_is_false_for_non_git_segments():
    assert mod._git_stages_secret("echo hi") is False
    assert mod._git_stages_secret("git status") is False
    assert mod._git_stages_secret("git add .env") is True


def test_git_secret_check_is_false_for_other_git_subcommands():
    assert mod._git_stages_secret("git log .env") is False
    assert mod._git_stages_secret("git add --dry-run .env") is False


# --- guard integrity, sensitive files, ADR sessions ---------------------------


def test_guard_integrity_ignores_files_outside_the_live_hooks_dir(tmp_path):
    live = tmp_path / "live-hooks"
    live.mkdir()
    other = tmp_path / "elsewhere" / "notes.py"
    with (
        patch.object(mod, "_live_hooks_dir", return_value=live.resolve()),
        patch.object(mod, "_is_worktree_on_feature_branch", return_value=False),
    ):
        assert _blocked_by(mod.check_guard_integrity, str(other)) is False
        assert _blocked_by(mod.check_guard_integrity, str(live / "gate.py")) is True


def test_sensitive_exception_is_false_for_a_plain_path():
    assert mod._is_sensitive_exception("/tmp/some/plain/.env") is False


def test_fixture_dir_exception_is_false_outside_a_repo():
    with patch.object(mod, "_repo_worktree_root", return_value=None):
        assert mod._is_sensitive_exception("/tmp/x/fixtures/.env") is False


def test_guard_patterns_skip_comments_and_blank_lines(tmp_path, monkeypatch):
    (tmp_path / ".guard-patterns").write_text("# a comment\n\n*.secret\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert [entry[2] for entry in mod._load_guard_patterns()] == ["*.secret"]


@pytest.mark.parametrize("content", ["[]", '"text"', "7"])
def test_adr_session_file_that_is_not_an_object_unlocks_nothing(tmp_path, content):
    (tmp_path / mod._ADR_SESSION_FILE).write_text(content, encoding="utf-8")
    target = tmp_path / "skills" / "new-skill" / "SKILL.md"
    assert mod._adr_registration_allows("new-skill", str(target), str(tmp_path)) is None

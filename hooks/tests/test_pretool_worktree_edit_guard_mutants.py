#!/usr/bin/env python3
"""Mutation-killing tests for pretool-worktree-edit-guard.

Covers behaviour the other suites never pinned: exit code 0 on every allow path,
cwds that only look like worktrees, worktree sub-directory cwds, a missing git
binary, junk file_path values ahead of a real escape, quiet stderr unless
CLAUDE_HOOKS_DEBUG is set, and the blocked governance record.

Run with: python3 -m pytest hooks/tests/test_pretool_worktree_edit_guard_mutants.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).parent.parent / "pretool-worktree-edit-guard.py"

MAIN_REPO = "/home/feedgen/road-to-aew"
WORKTREE = f"{MAIN_REPO}/.claude/worktrees/abc123"


def _run(event, home, *, env_extra=None, path=None, raw=None):
    """Run the hook as a subprocess; return (returncode, stdout, stderr)."""
    env = {k: v for k, v in os.environ.items() if k not in ("WORKTREE_EDIT_GUARD_BYPASS", "CLAUDE_HOOKS_DEBUG")}
    env["HOME"] = str(home)
    if path is not None:
        env["PATH"] = path
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=raw if raw is not None else json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _is_deny(stdout):
    if not stdout.strip():
        return False
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def _edit(file_path, cwd=WORKTREE, tool="Edit"):
    return {"tool_name": tool, "cwd": cwd, "tool_input": {"file_path": file_path}}


def test_bypass_env_exits_zero_and_stays_quiet(tmp_path):
    rc, out, err = _run(_edit(f"{MAIN_REPO}/src/a.ts"), tmp_path, env_extra={"WORKTREE_EDIT_GUARD_BYPASS": "1"})
    assert rc == 0
    assert out.strip() == ""
    assert err == ""


def test_bypass_with_debug_says_so_on_stderr(tmp_path):
    rc, out, err = _run(
        _edit(f"{MAIN_REPO}/src/a.ts"),
        tmp_path,
        env_extra={"WORKTREE_EDIT_GUARD_BYPASS": "1", "CLAUDE_HOOKS_DEBUG": "1"},
    )
    assert rc == 0
    assert err.strip() != ""


@pytest.mark.parametrize(
    "event,raw",
    [
        (None, "{ not json"),
        (None, "[1, 2, 3]"),
        ({"tool_name": "Bash", "cwd": WORKTREE, "tool_input": {"file_path": f"{MAIN_REPO}/a.ts"}}, None),
        ({"tool_name": "Edit", "cwd": WORKTREE, "tool_input": ["not", "a", "dict"]}, None),
    ],
    ids=["malformed-json", "non-dict-event", "unguarded-tool", "non-dict-tool-input"],
)
def test_pass_through_inputs_exit_zero_without_deny(tmp_path, event, raw):
    rc, out, _ = _run(event, tmp_path, raw=raw)
    assert rc == 0
    assert _is_deny(out) is False


def test_non_worktree_cwd_with_one_char_leaf_dir_may_edit_parent(tmp_path):
    """A plain project dir (not a worktree) never gets guarded, whatever its name."""
    cwd = tmp_path / "project" / "x"
    cwd.mkdir(parents=True)
    rc, out, _ = _run(_edit(str(tmp_path / "project" / "file.ts"), cwd=str(cwd)), tmp_path)
    assert rc == 0
    assert _is_deny(out) is False


def test_cwd_in_worktree_subdir_may_edit_elsewhere_in_worktree(tmp_path):
    rc, out, _ = _run(_edit(f"{WORKTREE}/lib/other.ts", cwd=f"{WORKTREE}/src"), tmp_path)
    assert rc == 0
    assert _is_deny(out) is False


def test_cwd_in_worktree_subdir_still_blocked_from_main_repo(tmp_path):
    rc, out, _ = _run(_edit(f"{MAIN_REPO}/lib/other.ts", cwd=f"{WORKTREE}/src"), tmp_path)
    assert rc == 0
    assert _is_deny(out) is True


def test_missing_git_binary_still_blocks_main_repo_escape(tmp_path):
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    rc, out, _ = _run(_edit(f"{MAIN_REPO}/src/foo.ts"), tmp_path, path=str(empty_bin))
    assert rc == 0
    assert _is_deny(out) is True


def test_junk_file_path_is_skipped_and_later_escape_still_blocked(tmp_path):
    event = {
        "tool_name": "MultiEdit",
        "cwd": WORKTREE,
        "tool_input": {"file_path": 123, "edits": [{"file_path": f"{MAIN_REPO}/src/a.ts"}]},
    }
    rc, out, _ = _run(event, tmp_path)
    assert rc == 0
    assert _is_deny(out) is True


def test_deny_is_quiet_beyond_reason_unless_debug(tmp_path):
    event = _edit(f"{MAIN_REPO}/src/a.ts")
    _, out, err = _run(event, tmp_path)
    assert _is_deny(out) is True
    assert len(err.strip().splitlines()) == 1
    _, _, err_debug = _run(event, tmp_path, env_extra={"CLAUDE_HOOKS_DEBUG": "1"})
    assert len(err_debug.strip().splitlines()) == 2


def test_deny_records_blocked_governance_event():
    spec = importlib.util.spec_from_file_location("wt_guard_mutants_mod", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    hook_utils = sys.modules["hook_utils"]
    calls = []
    env = {k: v for k, v in os.environ.items() if k not in ("WORKTREE_EDIT_GUARD_BYPASS", "CLAUDE_HOOKS_DEBUG")}
    with (
        patch.dict(os.environ, env, clear=True),
        patch.object(mod, "read_stdin", return_value=json.dumps(_edit(f"{MAIN_REPO}/src/a.ts"))),
        patch.object(hook_utils, "record_governance", lambda *_a, **kw: calls.append(kw)),
        patch.object(mod, "deny_tool_use", lambda *_a, **_kw: None),
        pytest.raises(SystemExit),
    ):
        mod.main()
    assert len(calls) == 1
    assert calls[0]["blocked"] is True

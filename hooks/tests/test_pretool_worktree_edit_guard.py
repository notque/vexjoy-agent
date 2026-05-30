#!/usr/bin/env python3
"""
Tests for the pretool-worktree-edit-guard hook.

Covers the 5 required cases plus path-prefix false-positive defenses.

Run with: python3 -m pytest hooks/tests/test_pretool_worktree_edit_guard.py -v
Or standalone: python3 hooks/tests/test_pretool_worktree_edit_guard.py
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

HOOK_PATH = Path(__file__).parent.parent / "pretool-worktree-edit-guard.py"

spec = importlib.util.spec_from_file_location("pretool_worktree_edit_guard", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A realistic main repo + worktree pair.
MAIN_REPO = "/home/feedgen/road-to-aew"
WT_ID = "abc123"
WORKTREE = f"{MAIN_REPO}/.claude/worktrees/{WT_ID}"


def _event(tool_name, *, cwd=None, file_path=None, notebook_path=None, edits=None, omit_cwd=False):
    tool_input = {}
    if file_path is not None:
        tool_input["file_path"] = file_path
    if notebook_path is not None:
        tool_input["notebook_path"] = notebook_path
    if edits is not None:
        tool_input["edits"] = edits
    ev = {"tool_name": tool_name, "tool_input": tool_input}
    if not omit_cwd:
        ev["cwd"] = cwd
    return json.dumps(ev)


def _run(stdin_payload, env=None):
    """Run main() in-process; return (exit_code, denied: bool)."""
    base_env = {k: v for k, v in os.environ.items() if k != mod._BYPASS_ENV}
    if env:
        base_env.update(env)

    captured = {}
    real_print = print

    def fake_print(*args, **kwargs):
        # Capture only stdout JSON (the deny decision), ignore stderr.
        if kwargs.get("file") in (None, sys.stdout):
            captured["stdout"] = (captured.get("stdout", "") + " ".join(str(a) for a in args)).strip()
        real_print(*args, **kwargs)

    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("builtins.print", fake_print),
    ):
        try:
            mod.main()
            code = 0
        except SystemExit as e:
            code = int(e.code) if e.code is not None else 0

    denied = False
    out = captured.get("stdout", "")
    if out:
        try:
            denied = json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
        except (json.JSONDecodeError, ValueError):
            denied = False
    return code, denied


# ---------------------------------------------------------------------------
# Required cases
# ---------------------------------------------------------------------------


def test_case1_worktree_agent_edits_main_repo_absolute_BLOCKS():
    payload = _event("Edit", cwd=WORKTREE, file_path=f"{MAIN_REPO}/src/foo.ts")
    code, denied = _run(payload)
    assert code == 0
    assert denied is True


def test_case2_worktree_agent_edits_in_worktree_file_ALLOWS():
    payload = _event("Edit", cwd=WORKTREE, file_path=f"{WORKTREE}/src/foo.ts")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case2b_relative_path_resolves_into_worktree_ALLOWS():
    payload = _event("Edit", cwd=WORKTREE, file_path="src/foo.ts")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case3_worktree_agent_edits_tmp_ALLOWS():
    payload = _event("Write", cwd=WORKTREE, file_path="/tmp/foo.png")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case3b_worktree_agent_edits_user_claude_ALLOWS():
    payload = _event("Write", cwd=WORKTREE, file_path="/home/feedgen/.claude/hooks/x.py")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case4_parent_session_main_repo_ALLOWS():
    # cwd is the main repo, NOT a worktree -> pass through.
    payload = _event("Edit", cwd=MAIN_REPO, file_path=f"{MAIN_REPO}/src/foo.ts")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case5_missing_cwd_fails_open():
    # No cwd key; falls back to os.getcwd() which is not a worktree -> ALLOW.
    payload = _event("Edit", omit_cwd=True, file_path=f"{MAIN_REPO}/src/foo.ts")
    code, denied = _run(payload)
    assert code == 0
    assert denied is False


def test_case5b_malformed_json_fails_open():
    code, denied = _run("{ not json")
    assert code == 0
    assert denied is False


# ---------------------------------------------------------------------------
# Extra hardening
# ---------------------------------------------------------------------------


def test_multiedit_main_repo_BLOCKS():
    payload = _event("MultiEdit", cwd=WORKTREE, file_path=f"{MAIN_REPO}/src/a.ts")
    code, denied = _run(payload)
    assert denied is True


def test_notebookedit_main_repo_BLOCKS():
    payload = _event("NotebookEdit", cwd=WORKTREE, notebook_path=f"{MAIN_REPO}/nb.ipynb")
    code, denied = _run(payload)
    assert denied is True


def test_notebookedit_in_worktree_ALLOWS():
    payload = _event("NotebookEdit", cwd=WORKTREE, notebook_path=f"{WORKTREE}/nb.ipynb")
    code, denied = _run(payload)
    assert denied is False


def test_sibling_repo_prefix_not_false_positive_ALLOWS():
    # "/home/feedgen/road-to-aew-evil" must NOT be treated as inside "/home/feedgen/road-to-aew".
    payload = _event("Edit", cwd=WORKTREE, file_path=f"{MAIN_REPO}-evil/src/foo.ts")
    code, denied = _run(payload)
    assert denied is False


def test_non_guarded_tool_ALLOWS():
    payload = _event("Bash", cwd=WORKTREE, file_path=f"{MAIN_REPO}/src/foo.ts")
    code, denied = _run(payload)
    assert denied is False


def test_bypass_env_ALLOWS():
    payload = _event("Edit", cwd=WORKTREE, file_path=f"{MAIN_REPO}/src/foo.ts")
    code, denied = _run(payload, env={mod._BYPASS_ENV: "1"})
    assert denied is False


# ---------------------------------------------------------------------------
# Standalone runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)

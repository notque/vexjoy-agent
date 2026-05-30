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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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
# Regression: symlinked roots (HIGH-1 C1/C2) and nested worktree-id (MEDIUM-1)
#
# These use REAL temp dirs + real git worktrees so the git-toplevel derivation
# and realpath canonicalization are exercised end to end. They skip gracefully
# where git or os.symlink is unavailable.
# ---------------------------------------------------------------------------

_HAS_GIT = shutil.which("git") is not None


def _git(args, cwd):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "HOME": cwd},
    )


def _init_repo(path):
    os.makedirs(path, exist_ok=True)
    _git(["init", "-q"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)
    Path(path, "seed.txt").write_text("seed\n")
    _git(["add", "seed.txt"], path)
    _git(["commit", "-q", "-m", "seed"], path)


def _make_real_worktree(base, worktree_relpath):
    """Create main repo at base/main and a git worktree at base/main/<relpath>.

    Returns (main_repo_root, worktree_root) as real (non-symlinked) abspaths.
    """
    main_repo = os.path.join(base, "main")
    _init_repo(main_repo)
    worktree_root = os.path.join(main_repo, worktree_relpath)
    os.makedirs(os.path.dirname(worktree_root), exist_ok=True)
    _git(["worktree", "add", "-q", worktree_root, "-b", "wt-branch"], main_repo)
    return main_repo, worktree_root


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_symlinked_root_out_of_worktree_escape_BLOCKS():
    """HIGH-1 C1: under a symlinked path, a main-repo escape is still BLOCKED."""
    base = tempfile.mkdtemp(prefix="wtguard_sym_")
    try:
        main_repo, worktree_root = _make_real_worktree(base, ".claude/worktrees/abc123")
        # Symlink the whole base so the agent's cwd is a symlinked path.
        link = os.path.join(tempfile.mkdtemp(prefix="wtguard_link_"), "linked")
        try:
            os.symlink(base, link)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
        linked_cwd = os.path.join(link, "main", ".claude", "worktrees", "abc123")
        # Target: a main-repo file via the SYMLINKED absolute path (the escape).
        target = os.path.join(link, "main", "src", "foo.ts")
        payload = _event("Edit", cwd=linked_cwd, file_path=target)
        code, denied = _run(payload)
        assert code == 0
        assert denied is True, "symlinked out-of-worktree escape must be blocked"
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_symlinked_root_in_worktree_edit_ALLOWS():
    """HIGH-1 C2: under a symlinked path, a legitimate in-worktree edit is ALLOWED."""
    base = tempfile.mkdtemp(prefix="wtguard_sym_")
    try:
        main_repo, worktree_root = _make_real_worktree(base, ".claude/worktrees/abc123")
        link = os.path.join(tempfile.mkdtemp(prefix="wtguard_link_"), "linked")
        try:
            os.symlink(base, link)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
        linked_cwd = os.path.join(link, "main", ".claude", "worktrees", "abc123")
        # Target: a file INSIDE the worktree via the symlinked path.
        target = os.path.join(linked_cwd, "src", "foo.ts")
        payload = _event("Edit", cwd=linked_cwd, file_path=target)
        code, denied = _run(payload)
        assert code == 0
        assert denied is False, "symlinked in-worktree edit must be allowed"
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_nested_worktree_id_sibling_edit_BLOCKS():
    """MEDIUM-1: with a nested .../worktrees/<group>/<id>/ layout, an edit into a
    SIBLING worktree (same group, different id) must be BLOCKED.

    The single-segment string-split would compute worktree_root as
    .../worktrees/<group> (too shallow) and treat the sibling as in-tree ->
    under-block. The git-toplevel derivation pins worktree_root to the actual
    worktree, so the sibling is correctly outside it.
    """
    base = tempfile.mkdtemp(prefix="wtguard_nest_")
    try:
        main_repo = os.path.join(base, "main")
        _init_repo(main_repo)
        wt_a = os.path.join(main_repo, ".claude/worktrees/group1/idA")
        wt_b = os.path.join(main_repo, ".claude/worktrees/group1/idB")
        os.makedirs(os.path.dirname(wt_a), exist_ok=True)
        _git(["worktree", "add", "-q", wt_a, "-b", "branch-a"], main_repo)
        _git(["worktree", "add", "-q", wt_b, "-b", "branch-b"], main_repo)
        # Agent runs in idA; tries to edit a file in sibling idB.
        target = os.path.join(wt_b, "src", "foo.ts")
        payload = _event("Edit", cwd=wt_a, file_path=target)
        code, denied = _run(payload)
        assert code == 0
        assert denied is True, "sibling-worktree edit under nested id must be blocked"
    finally:
        shutil.rmtree(base, ignore_errors=True)


@pytest.mark.skipif(not _HAS_GIT, reason="git not available")
def test_nested_worktree_id_in_worktree_edit_ALLOWS():
    """MEDIUM-1 companion: an edit INSIDE the agent's own nested worktree is ALLOWED."""
    base = tempfile.mkdtemp(prefix="wtguard_nest_")
    try:
        main_repo = os.path.join(base, "main")
        _init_repo(main_repo)
        wt_a = os.path.join(main_repo, ".claude/worktrees/group1/idA")
        os.makedirs(os.path.dirname(wt_a), exist_ok=True)
        _git(["worktree", "add", "-q", wt_a, "-b", "branch-a"], main_repo)
        target = os.path.join(wt_a, "src", "foo.ts")
        payload = _event("Edit", cwd=wt_a, file_path=target)
        code, denied = _run(payload)
        assert code == 0
        assert denied is False, "own nested-worktree edit must be allowed"
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# Standalone runner (no pytest required)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _skipped_exc = getattr(getattr(pytest, "skip", None), "Exception", Exception)
    try:
        from _pytest.outcomes import Skipped as _skipped_exc  # type: ignore
    except Exception:
        pass

    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failures = 0
    skipped = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except _skipped_exc as e:  # type: ignore[misc]
            skipped += 1
            print(f"SKIP  {name}: {e}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures - skipped}/{len(tests)} passed, {skipped} skipped")
    sys.exit(1 if failures else 0)

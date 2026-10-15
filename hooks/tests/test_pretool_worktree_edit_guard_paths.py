#!/usr/bin/env python3
"""Path-resolution tests for pretool-worktree-edit-guard.

Added from the E2 mutation check: the existing suite never sent a relative path
that climbs out of the worktree, or a per-edit `edits[].file_path` that points at
the main repo, so hooks that skipped either check still passed every test.

Each test runs the hook as a subprocess with a throwaway HOME.

Run with: python3 -m pytest hooks/tests/test_pretool_worktree_edit_guard_paths.py -v
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "pretool-worktree-edit-guard.py"

MAIN_REPO = "/home/feedgen/road-to-aew"
WORKTREE = f"{MAIN_REPO}/.claude/worktrees/abc123"


def _denied(event: dict, home: Path) -> bool:
    env = {k: v for k, v in os.environ.items() if k != "WORKTREE_EDIT_GUARD_BYPASS"}
    env["HOME"] = str(home)
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout.strip():
        return False
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_relative_path_climbing_out_of_worktree_is_denied(tmp_path):
    event = {
        "tool_name": "Edit",
        "cwd": WORKTREE,
        "tool_input": {"file_path": "../../../src/foo.ts"},
    }
    assert _denied(event, tmp_path) is True


def test_relative_path_staying_inside_worktree_is_allowed(tmp_path):
    event = {
        "tool_name": "Edit",
        "cwd": WORKTREE,
        "tool_input": {"file_path": "../abc123/src/foo.ts"},
    }
    assert _denied(event, tmp_path) is False


def test_multiedit_per_edit_main_repo_path_is_denied(tmp_path):
    event = {
        "tool_name": "MultiEdit",
        "cwd": WORKTREE,
        "tool_input": {
            "file_path": f"{WORKTREE}/src/ok.ts",
            "edits": [{"file_path": f"{MAIN_REPO}/src/escape.ts"}],
        },
    }
    assert _denied(event, tmp_path) is True


def test_multiedit_skips_junk_edits_and_still_denies_later_escape(tmp_path):
    event = {
        "tool_name": "MultiEdit",
        "cwd": WORKTREE,
        "tool_input": {
            "file_path": f"{WORKTREE}/src/ok.ts",
            "edits": ["not-a-dict", {"old_string": "a"}, {"file_path": f"{MAIN_REPO}/src/escape.ts"}],
        },
    }
    assert _denied(event, tmp_path) is True


def test_multiedit_per_edit_worktree_paths_are_allowed(tmp_path):
    event = {
        "tool_name": "MultiEdit",
        "cwd": WORKTREE,
        "tool_input": {
            "file_path": f"{WORKTREE}/src/ok.ts",
            "edits": [{"file_path": f"{WORKTREE}/src/also-ok.ts"}, {"old_string": "a"}],
        },
    }
    assert _denied(event, tmp_path) is False

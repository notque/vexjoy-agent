#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Bash Hook: Branch Safety Gate

Blocks git commit commands when the current working branch is main or master.
Forces agents to create a feature branch before committing.

This is a HARD GATE — exit 2 blocks the Bash tool.

Detection logic:
- Tool is Bash
- Command contains 'git commit'
- Current branch is 'main' or 'master' (checked via git branch --show-current)

Allow-through conditions:
- Tool is not Bash
- Command does not contain 'git commit'
- Current branch is NOT main or master
- BRANCH_SAFETY_BYPASS=1 env var
"""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import record_governance_event
from stdin_timeout import read_stdin

_BYPASS_ENV = "BRANCH_SAFETY_BYPASS"
_PROTECTED_BRANCHES = {"main", "master"}


def _current_branch(cwd: str | None) -> str | None:
    """Return the current git branch name, or None on error."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd or None,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    # tool_name filter removed — matcher "Bash" in settings.json prevents
    # this hook from spawning for non-Bash tools.

    command = event.get("tool_input", {}).get("command", "")
    if "git commit" not in command:
        sys.exit(0)

    # Bypass env var — set when an explicit override is needed.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[branch-safety] Bypassed via BRANCH_SAFETY_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    cwd = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    branch = _current_branch(cwd)

    if debug:
        print(f"[branch-safety] git commit detected, branch={branch!r}", file=sys.stderr)

    if branch is None:
        # Cannot determine branch — fail open rather than block valid work.
        if debug:
            print("[branch-safety] Could not determine branch — allowing through", file=sys.stderr)
        sys.exit(0)

    if branch in _PROTECTED_BRANCHES:
        print(
            f"[branch-safety] BLOCKED: Cannot commit directly to {branch}. Create a feature branch first.",
            file=sys.stderr,
        )
        print("[fix-with-skill] git-commit-flow", file=sys.stderr)
        try:
            record_governance_event(
                "policy_violation", tool_name="Bash", hook_phase="pre", severity="high", blocked=True
            )
        except Exception:
            pass  # Never let recording prevent a block
        sys.exit(2)

    if debug:
        print(f"[branch-safety] Branch {branch!r} is not protected — allowing through", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception as e:
        if os.environ.get("CLAUDE_HOOKS_DEBUG"):
            traceback.print_exc(file=sys.stderr)
        else:
            print(f"[branch-safety] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never exit 2 on unexpected errors.
        sys.exit(0)

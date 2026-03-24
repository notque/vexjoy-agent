#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse Hook: Block git add -f on gitignored paths and .gitignore edits.

Prevents agents and subagents from:
1. Using `git add -f` / `git add --force` to bypass .gitignore
2. Modifying .gitignore itself (safety boundary file)

Design:
- Early-exit for non-Bash tools (<1ms)
- Fast string matching before any subprocess calls
- Returns exit code 2 to BLOCK the tool if violation found
- Sub-50ms execution
- Graduated from incident: two worktree agents force-added gitignored files,
  another modified .gitignore to un-ignore protected paths
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin


def main() -> None:
    try:
        hook_input = json.loads(read_stdin(timeout=2))
        tool_name = hook_input.get("tool_name", "")

        # Fast path: only care about Bash
        if tool_name != "Bash":
            sys.exit(0)

        command = hook_input.get("tool_input", {}).get("command", "")
        if not command:
            sys.exit(0)

        # Block 1: .gitignore modification attempts
        # Only match direct file operations, not .gitignore mentioned in strings/heredocs
        # Split on heredoc boundaries — only check the command part, not body content
        cmd_part = command.split("<<")[0] if "<<" in command else command
        if (
            re.search(r"(>|>>)\s*\.gitignore", cmd_part)
            or re.search(r"(sed|awk|tee)\s+\S*\s*\.gitignore", cmd_part)
            or re.search(r"mv\s+\S+\s+\.gitignore", cmd_part)
        ):
            print("[BLOCKED] Agents must not modify .gitignore.")
            print("This file controls repository safety boundaries.")
            sys.exit(2)

        # Fast path: no git add in command
        if "git add" not in command:
            sys.exit(0)

        # Block 2: git add with force flags
        if not re.search(r"git\s+add\s+.*(-f|--force)", command):
            sys.exit(0)

        # Extract paths being force-added
        parts = command.split()
        try:
            add_idx = parts.index("add")
        except ValueError:
            sys.exit(0)

        paths = []
        past_separator = False
        for part in parts[add_idx + 1 :]:
            if part == "--":
                past_separator = True
                continue
            if part.startswith("-") and not past_separator:
                continue
            paths.append(part)

        if not paths:
            # git add -f with no paths — let git handle it
            sys.exit(0)

        # Check which paths are gitignored
        try:
            result = subprocess.run(["git", "check-ignore"] + paths, capture_output=True, text=True, timeout=3)
            ignored = [p for p in result.stdout.strip().split("\n") if p]
        except (subprocess.TimeoutExpired, OSError):
            sys.exit(0)  # Don't block on check failure

        if ignored:
            print(f"[BLOCKED] git add -f on gitignored paths: {', '.join(ignored)}")
            print("These paths are gitignored for a reason. Do not force-add them.")
            sys.exit(2)

        sys.exit(0)

    except (json.JSONDecodeError, KeyError, Exception):
        sys.exit(0)  # Never block on parse errors


if __name__ == "__main__":
    main()

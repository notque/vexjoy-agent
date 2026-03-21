#!/usr/bin/env python3
"""Perses Lint Gate Hook.

Blocks raw `percli apply` commands and redirects to the perses-lint skill
to ensure validation before deployment.

Event: PreToolUse (Bash)
"""

import json
import re
import sys


def main():
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        # Fail open: if we can't parse the event, allow the tool to run.
        # Exit code 2 = block in Claude Code; broken hooks must not block.
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # Detect percli apply without prior lint
    if re.search(r"percli\s+apply", command):
        # Check if lint was also in the command chain
        if not re.search(r"percli\s+lint", command):
            print(
                "[perses-lint-gate] BLOCKED: percli apply detected without percli lint.\n"
                "Run `percli lint -f <file>` first to validate resources.\n"
                "[fix-with-skill] perses-lint"
            )
            # Exit 2 to block the tool use
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A broken hook must fail OPEN (exit 0), not fail CLOSED (exit 2).
        # Python's default error exit code is 2, which Claude Code interprets
        # as "block this tool" — causing a deadlock if the hook crashes.
        sys.exit(0)

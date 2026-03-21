#!/usr/bin/env python3
"""
PreToolUse:Bash Hook: Git Submission Gate

Blocks raw git push, gh pr create, and gh pr merge commands that bypass
quality gate skills (pr-sync, pr-pipeline). Forces the LLM to route
through proper skills that run review loops before submission.

This is a HARD GATE — it physically prevents the command from executing.
The LLM receives a [fix-with-skill] directive telling it which skill to use.

Bypass: Skills that legitimately need to run these commands prefix them with
CLAUDE_GATE_BYPASS=1 in the command string. The hook detects this prefix
and allows passthrough. Example:
    CLAUDE_GATE_BYPASS=1 git push -u origin branch

Design Principles:
- Sub-5ms for non-matching commands (early exit)
- Blocks with exit 2 + stderr message
- Non-blocking for read-only git operations (status, diff, log, branch)
- Passthrough when command contains CLAUDE_GATE_BYPASS=1 prefix
- Intentionally matches inside strings/comments — over-blocking preferred
"""

import json
import re
import sys

# Bypass prefix that skills include when they legitimately need to run blocked commands.
# Checked as a string prefix in the command, not as an env var.
_BYPASS_PREFIX = "CLAUDE_GATE_BYPASS=1"

# Commands that MUST go through skills, not raw Bash.
# \b ensures "git stash push" does not match (stash breaks word boundary before push).
BLOCKED_PATTERNS = [
    (re.compile(r"\bgit\s+push\b"), "pr-sync", "Use /pr-sync to push (runs review loop first)"),
    (re.compile(r"\bgh\s+pr\s+create\b"), "pr-pipeline", "Use /pr-pipeline to create PR (runs review loop first)"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "pr-pipeline", "Use /pr-pipeline to merge (requires review to pass first)"),
]


def main() -> None:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Skills prefix blocked commands with CLAUDE_GATE_BYPASS=1 to pass through
    if command.lstrip().startswith(_BYPASS_PREFIX):
        sys.exit(0)

    for pattern, skill_name, message in BLOCKED_PATTERNS:
        if pattern.search(command):
            print(
                f"[git-submission-gate] BLOCKED: {message}\n[fix-with-skill] {skill_name}",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()

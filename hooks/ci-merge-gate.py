#!/usr/bin/env python3
"""PreToolUse hook: Block gh pr merge when CI checks haven't passed.

Intercepts Bash tool calls containing 'gh pr merge' and checks GitHub
Actions status before allowing the merge. Blocks if any checks are
failing or still pending.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin


def main() -> None:
    data = json.loads(read_stdin(timeout=2))

    tool = data.get("tool_name", "")
    if tool != "Bash":
        return

    command = data.get("tool_input", {}).get("command", "")

    # Only intercept gh pr merge commands
    if "gh pr merge" not in command and "gh pr merge" not in command.replace("  ", " "):
        return

    # Extract PR number from command
    # Patterns: gh pr merge 55, gh pr merge #55, gh pr merge --squash 55
    parts = command.split()
    pr_number = None
    for i, part in enumerate(parts):
        if part.lstrip("#").isdigit() and i > 0 and parts[i - 1] != "--count":
            pr_number = part.lstrip("#")
            break

    if not pr_number:
        # No PR number found — might be merging current branch PR
        # Try to get it from current branch
        try:
            result = subprocess.run(
                ["gh", "pr", "view", "--json", "number", "--jq", ".number"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip().isdigit():
                pr_number = result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if not pr_number:
        # Can't determine PR number — let it through with a warning
        print("[ci-merge-gate] WARNING: Could not determine PR number. Skipping CI check.")
        return

    # Check CI status
    try:
        result = subprocess.run(
            ["gh", "pr", "checks", pr_number, "--json", "name,state,conclusion"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("[ci-merge-gate] WARNING: Could not check CI status (gh not available or timeout).")
        return

    if result.returncode != 0:
        # gh pr checks failed — might be no checks configured
        if "no checks" in result.stderr.lower():
            return
        print(f"[ci-merge-gate] WARNING: Could not fetch CI checks: {result.stderr.strip()}")
        return

    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("[ci-merge-gate] WARNING: Could not parse CI check results.")
        return

    failing = [c for c in checks if c.get("conclusion") == "failure"]
    pending = [c for c in checks if c.get("state") in ("pending", "queued", "in_progress")]

    if failing:
        names = ", ".join(c["name"] for c in failing)
        print(f"[ci-merge-gate] BLOCKED: CI checks failing: {names}")
        print(f"[ci-merge-gate] Fix the failing checks before merging PR #{pr_number}.")
        # Exit non-zero to block the tool call
        sys.exit(2)

    if pending:
        names = ", ".join(c["name"] for c in pending)
        print(f"[ci-merge-gate] BLOCKED: CI checks still running: {names}")
        print(f"[ci-merge-gate] Wait for checks to complete before merging PR #{pr_number}.")
        sys.exit(2)

    # All checks passed
    print(f"[ci-merge-gate] CI checks passed for PR #{pr_number}. Merge allowed.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let intentional exit(2) blocks propagate
    except Exception:
        sys.exit(0)  # Fail-open: crashed hook must never block tools

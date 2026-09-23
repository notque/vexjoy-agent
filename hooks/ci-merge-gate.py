#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse hook: Block gh pr merge when CI checks haven't passed.

Intercepts Bash tool calls containing 'gh pr merge' and checks GitHub
Actions status before allowing the merge. Blocks if any checks are
failing or still pending.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from hook_utils import deny_tool_use, record_governance
from stdin_timeout import read_stdin

_MERGE_RE = re.compile(r"\bgh\s+pr\s+merge\b")
# Tokens that end the merge simple command.
_SEGMENT_END = {"&&", "||", ";", "|", "&", "\n", "(", ")"}
# Merge flags that take a value; the value is never the PR number.
_VALUE_FLAGS = {
    "-t",
    "--subject",
    "-b",
    "--body",
    "-F",
    "--body-file",
    "-A",
    "--author-email",
    "--match-head-commit",
    "-R",
    "--repo",
}
_PULL_URL_RE = re.compile(r"/pull/(\d+)")


def extract_pr_number(command: str) -> str | None:
    """Return the PR number from the first merge command's argument list.

    Parses only the tokens after the merge subcommand up to the first shell
    separator or redirection. Returns None when no numeric or URL selector
    is given (the caller then falls back to the current branch).
    """
    m = _MERGE_RE.search(command)
    if not m:
        return None
    rest = command[m.end() :]
    # Drop fd prefixes on redirects (`2>&1`) so the fd is not read as an argument.
    rest = re.sub(r"(?<!\S)\d+(?=[<>])", " ", rest)
    lex = shlex.shlex(rest, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""  # `#55` is a PR selector, not a comment
    try:
        tokens = list(lex)
    except ValueError:
        tokens = rest.split()
    skip_next = False
    for tok in tokens:
        if tok in _SEGMENT_END or tok[:1] in "<>" or tok.startswith(("&", "|", ";")):
            break
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("-"):
            if tok in _VALUE_FLAGS:
                skip_next = True
            continue
        # First positional argument is the PR selector.
        if tok.lstrip("#").isdigit():
            return tok.lstrip("#")
        url = _PULL_URL_RE.search(tok)
        return url.group(1) if url else None
    return None


def main() -> None:
    data = json.loads(read_stdin(timeout=2))

    # tool_name filter removed — matcher "Bash" in settings.json prevents
    # this hook from spawning for non-Bash tools.

    command = data.get("tool_input", {}).get("command", "")

    # Only intercept gh pr merge commands
    if "gh pr merge" not in command and "gh pr merge" not in command.replace("  ", " "):
        return

    parts = command.split()

    # --- Block --admin before any CI check ---
    if "--admin" in parts:
        if os.environ.get("ALLOW_ADMIN_MERGE") == "1":
            print("[ci-merge-gate] WARNING: --admin override allowed via ALLOW_ADMIN_MERGE=1", file=sys.stderr)
        else:
            print("[ci-merge-gate] BLOCKED: --admin bypasses branch protection", file=sys.stderr)
            deny_tool_use("PreToolUse", "Use of --admin bypasses CI checks. Remove --admin and wait for CI to pass.")
            sys.exit(0)

    # --- Block --force before any CI check ---
    if "--force" in parts:
        if os.environ.get("ALLOW_FORCE_MERGE") == "1":
            print("[ci-merge-gate] WARNING: --force override allowed via ALLOW_FORCE_MERGE=1", file=sys.stderr)
        else:
            print("[ci-merge-gate] BLOCKED: --force bypasses merge safeguards", file=sys.stderr)
            deny_tool_use("PreToolUse", "Use of --force bypasses merge safeguards. Remove --force and merge normally.")
            sys.exit(0)

    # PR number comes from the merge-command arguments only, never from
    # other commands in the chain (`sleep 5 && <merge> 1012`).
    pr_number = extract_pr_number(command)

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
        print("[ci-merge-gate] WARNING: Could not determine PR number. Skipping CI check.", file=sys.stderr)
        return

    # Check CI status
    try:
        result = subprocess.run(
            ["gh", "pr", "checks", pr_number, "--json", "name,state,bucket"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(
            "[ci-merge-gate] WARNING: Could not check CI status (gh not available or timeout).",
            file=sys.stderr,
        )
        return

    if result.returncode != 0:
        # gh pr checks failed — might be no checks configured
        if "no checks" in result.stderr.lower():
            return
        print(
            f"[ci-merge-gate] WARNING: Could not fetch CI checks: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return

    try:
        checks = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("[ci-merge-gate] WARNING: Could not parse CI check results.", file=sys.stderr)
        return

    # bucket field values: pass, fail, pending, skipping, cancel
    failing = [c for c in checks if c.get("bucket") == "fail"]
    pending = [c for c in checks if c.get("bucket") == "pending"]

    if failing:
        names = ", ".join(c["name"] for c in failing)
        print(f"[ci-merge-gate] BLOCKED: CI checks failing: {names}", file=sys.stderr)
        print(f"[ci-merge-gate] Fix the failing checks before merging PR #{pr_number}.", file=sys.stderr)
        record_governance(
            "approval_requested",
            hook_name="ci-merge-gate",
            tool_name="Bash",
            hook_phase="pre",
            severity="medium",
            blocked=True,
            command=command,
        )
        deny_tool_use(
            "PreToolUse",
            f"CI checks are failing for PR #{pr_number}: {names}. Fix the failing checks before merging.",
        )
        sys.exit(0)

    if pending:
        names = ", ".join(c["name"] for c in pending)
        print(f"[ci-merge-gate] BLOCKED: CI checks still running: {names}", file=sys.stderr)
        print(f"[ci-merge-gate] Wait for checks to complete before merging PR #{pr_number}.", file=sys.stderr)
        record_governance(
            "approval_requested",
            hook_name="ci-merge-gate",
            tool_name="Bash",
            hook_phase="pre",
            severity="medium",
            blocked=True,
            command=command,
        )
        deny_tool_use(
            "PreToolUse",
            f"CI checks are still running for PR #{pr_number}: {names}. "
            "Wait for all checks to complete before merging.",
        )
        sys.exit(0)

    # All checks passed
    # PreToolUse stdout is protocol-only. Human-readable diagnostics must use
    # stderr or Codex's adapter will reject an otherwise allowed invocation.
    print(f"[ci-merge-gate] CI checks passed for PR #{pr_number}. Merge allowed.", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        print(f"[ci-merge-gate] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)  # Fail-open: crashed hook must never block tools

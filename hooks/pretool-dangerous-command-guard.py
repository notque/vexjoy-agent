#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Bash Hook: Dangerous Command Guard

Blocks known-destructive shell commands before execution. Defense in depth
against catastrophic mistakes like `rm -rf /`, `DROP DATABASE`, or
`kubectl delete namespace production`.

This is a HARD GATE — exit 2 blocks the command. The user sees the
blocked pattern and can add it to .guard-whitelist to override.

Pattern categories:
- Filesystem destruction (rm -rf on system paths)
- Database destruction (DROP DATABASE, DROP SCHEMA, TRUNCATE)
- Permission escalation (chmod 777)
- Force-push to protected branches
- Container mass-kill (docker rm -f all, kubectl delete namespace)
- System-level danger (mkfs, dd, fork bomb)
- Cloud destructive (terraform destroy, aws s3 rb --force)

Per-project whitelist: .guard-whitelist (one pattern per line).
Bypass: DANGEROUS_GUARD_BYPASS=1 env var.

Performance target: <10ms (compiled regex, no subprocess calls).

ADR: adr/012-dangerous-command-guard.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "DANGEROUS_GUARD_BYPASS"

# Each tuple: (compiled_regex, category, human_description)
DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Filesystem destruction — only system/root paths, not arbitrary directories
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/\s*$"), "filesystem", "rm -rf /"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/\*"), "filesystem", "rm -rf /*"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+~/?(\s|$)"), "filesystem", "rm -rf ~"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+\./?(\s|$)"), "filesystem", "rm -rf ."),
    # Database destruction
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "database", "DROP DATABASE"),
    (re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE), "database", "DROP SCHEMA"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "database", "TRUNCATE TABLE"),
    # Permission escalation
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "permissions", "chmod 777"),
    # Force-push to protected branches
    (re.compile(r"\bgit\s+push\s+.*--force\s+.*\b(main|master)\b"), "git", "git push --force main/master"),
    (re.compile(r"\bgit\s+push\s+-f\s+.*\b(main|master)\b"), "git", "git push -f main/master"),
    # Container mass-kill
    (re.compile(r"\bdocker\s+system\s+prune\s+-af\b"), "container", "docker system prune -af"),
    (re.compile(r"\bkubectl\s+delete\s+namespace\b"), "container", "kubectl delete namespace"),
    (re.compile(r"\bkubectl\s+delete\s+ns\b"), "container", "kubectl delete ns"),
    # System-level danger
    (re.compile(r"\bmkfs\b"), "system", "mkfs (format disk)"),
    (re.compile(r"\bdd\s+if="), "system", "dd (raw disk write)"),
    # Cloud destructive
    (re.compile(r"\bterraform\s+destroy\b(?!.*-target)"), "cloud", "terraform destroy (no -target)"),
    (re.compile(r"\baws\s+s3\s+rb\s+.*--force\b"), "cloud", "aws s3 rb --force"),
]


def _load_whitelist() -> list[str]:
    """Load per-project whitelist from .guard-whitelist if it exists."""
    whitelist_path = Path.cwd() / ".guard-whitelist"
    if not whitelist_path.is_file():
        return []
    try:
        return [
            line.strip()
            for line in whitelist_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except OSError:
        return []


def _is_whitelisted(command: str, whitelist: list[str]) -> bool:
    """Check if the command matches any whitelist entry."""
    for entry in whitelist:
        if entry in command:
            return True
    return False


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    # Check bypass env var
    if os.environ.get(_BYPASS_ENV) == "1":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")
    if not command:
        sys.exit(0)

    # Check each dangerous pattern
    for pattern, category, description in DANGEROUS_PATTERNS:
        if pattern.search(command):
            # Check whitelist before blocking
            whitelist = _load_whitelist()
            if _is_whitelisted(command, whitelist):
                sys.exit(0)

            print(
                f"[dangerous-command-guard] BLOCKED: {description} ({category})\n"
                f"[dangerous-command-guard] Command: {command}\n"
                f"[dangerous-command-guard] To allow: add pattern to .guard-whitelist",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail OPEN — never deadlock due to guard crash.
        sys.exit(0)

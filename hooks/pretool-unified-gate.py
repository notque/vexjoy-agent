#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Unified Gate (ADR-068)

Consolidates 5 PreToolUse gate hooks into a single entry point:
1. block-gitignore-bypass   — Bash: blocks git add -f on gitignored paths & .gitignore edits
2. pretool-git-submission-gate — Bash: blocks raw git push, gh pr create/merge
3. pretool-dangerous-command-guard — Bash: blocks destructive commands
4. pretool-creation-gate    — Write: blocks new agent/skill file creation
5. pretool-sensitive-file-guard — Write+Edit: blocks writes to .env, credentials, SSH keys, etc.

Attribution blocking removed: use settings.json {"attribution": {"commit": "", "pr": ""}} instead.
Each check preserves its original stderr prefix and bypass mechanism.
Exit 2 = block. Exit 0 = allow. Entire main() wrapped in try/except to fail OPEN.

Performance: <50ms. Early-exit for non-matching tools. Only gitignore bypass uses subprocess.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import record_governance_event
from stdin_timeout import read_stdin

# ═══════════════════════════════════════════════════════════════
# 1. GITIGNORE BYPASS (block-gitignore-bypass.py)
# ═══════════════════════════════════════════════════════════════

# (patterns are inline in check_gitignore_bypass function)

# ═══════════════════════════════════════════════════════════════
# 2. GIT SUBMISSION PATTERNS (pretool-git-submission-gate.py)
# ═══════════════════════════════════════════════════════════════

_GIT_SUBMISSION_BYPASS = "CLAUDE_GATE_BYPASS=1"

_GIT_SUBMISSION_PATTERNS = [
    (re.compile(r"\bgit\s+push\b"), "pr-sync", "Use /pr-sync to push (runs review loop first)"),
    (re.compile(r"\bgh\s+pr\s+create\b"), "pr-pipeline", "Use /pr-pipeline to create PR (runs review loop first)"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "pr-pipeline", "Use /pr-pipeline to merge (requires review to pass first)"),
]

# ═══════════════════════════════════════════════════════════════
# 3. DANGEROUS COMMAND PATTERNS (pretool-dangerous-command-guard.py)
# ═══════════════════════════════════════════════════════════════

_DANGEROUS_BYPASS_ENV = "DANGEROUS_GUARD_BYPASS"

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Filesystem destruction
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

# ═══════════════════════════════════════════════════════════════
# 4. CREATION GATE PATTERNS (pretool-creation-gate.py)
# ═══════════════════════════════════════════════════════════════

_CREATION_BYPASS_ENV = "CREATION_GATE_BYPASS"

_AGENT_PATTERN = re.compile(r"/agents/[^/]+\.md$")
_SKILL_PATTERN = re.compile(r"/(skills|pipelines)/[^/]+/SKILL\.md$")

# ═══════════════════════════════════════════════════════════════
# 5. SENSITIVE FILE PATTERNS (pretool-sensitive-file-guard.py)
# ═══════════════════════════════════════════════════════════════

_SENSITIVE_BYPASS_ENV = "SENSITIVE_FILE_GUARD_BYPASS"

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Environment files (except .env.example)
    (re.compile(r"/\.env$"), "env", ".env"),
    (re.compile(r"/\.env\.(local|production|staging|development|dev|prod)$"), "env", ".env.*"),
    # Credential files
    (re.compile(r"/credentials\.(json|yml|yaml)$"), "credentials", "credentials file"),
    (re.compile(r"/service-account[^/]*\.json$"), "credentials", "service account JSON"),
    # SSH keys
    (re.compile(r"/\.ssh/"), "ssh", "SSH directory"),
    (re.compile(r"/id_(rsa|ed25519|ecdsa|dsa)$"), "ssh", "SSH private key"),
    # Private key / certificate files
    (re.compile(r"\.p12$"), "certificate", ".p12 certificate"),
    (re.compile(r"\.pfx$"), "certificate", ".pfx certificate"),
    (re.compile(r"\.key$"), "certificate", ".key private key"),
    # Cloud configs
    (re.compile(r"\.aws/credentials$"), "cloud", "AWS credentials"),
    (re.compile(r"\.kube/config$"), "cloud", "kubeconfig"),
    (re.compile(r"\.gcloud/"), "cloud", "gcloud config directory"),
    # Token files
    (re.compile(r"/token\.json$"), "token", "token.json"),
    (re.compile(r"/\.tokens$"), "token", ".tokens file"),
]

_SENSITIVE_EXCEPTIONS: list[re.Pattern[str]] = [
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.sample$"),
    re.compile(r"\.env\.template$"),
    re.compile(r"/testdata/"),
    re.compile(r"/fixtures/"),
    re.compile(r"/__fixtures__/"),
    re.compile(r"/test_?data/"),
]


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_guard_whitelist() -> list[str]:
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


def _load_guard_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Load per-project sensitive patterns from .guard-patterns."""
    guard_path = Path.cwd() / ".guard-patterns"
    if not guard_path.is_file():
        return []
    extra = []
    try:
        for line in guard_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                regex = line.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                extra.append((re.compile(regex), "custom", line))
    except OSError:
        pass
    return extra


def _is_sensitive_exception(file_path: str) -> bool:
    """Check if file matches a sensitive-file exception pattern."""
    return any(p.search(file_path) for p in _SENSITIVE_EXCEPTIONS)


def _block(message: str, tool_name: str = "") -> None:
    """Print block message to stderr and exit 2."""
    print(message, file=sys.stderr)
    try:
        record_governance_event("hook_blocked", tool_name=tool_name, hook_phase="pre", severity="high", blocked=True)
    except Exception:
        pass  # Never let recording prevent a block
    sys.exit(2)


# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — each returns normally (allow) or calls _block (exit 2)
# ═══════════════════════════════════════════════════════════════


def check_gitignore_bypass(command: str) -> None:
    """Block git add -f on gitignored paths and .gitignore edits."""
    # Block 1: .gitignore modification attempts
    cmd_part = command.split("<<")[0] if "<<" in command else command
    if (
        re.search(r"(>|>>)\s*\.gitignore", cmd_part)
        or re.search(r"(sed|awk|tee)\b.*\.gitignore", cmd_part)
        or re.search(r"mv\s+\S+\s+\.gitignore", cmd_part)
    ):
        _block(
            "[gitignore-bypass] BLOCKED: Agents must not modify .gitignore.\n"
            "[gitignore-bypass] This file controls repository safety boundaries."
        )

    # Fast path: no git add in command
    if "git add" not in command:
        return

    # Block 2: git add with force flags
    if not re.search(r"git\s+add\s+.*(-f|--force)", command):
        return

    # Extract paths being force-added
    parts = command.split()
    try:
        add_idx = parts.index("add")
    except ValueError:
        return

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
        return

    # Check which paths are gitignored
    try:
        result = subprocess.run(
            ["git", "check-ignore"] + paths,
            capture_output=True,
            text=True,
            timeout=3,
        )
        ignored = [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, OSError):
        return  # Don't block on check failure

    if ignored:
        _block(
            f"[gitignore-bypass] BLOCKED: git add -f on gitignored paths: {', '.join(ignored)}\n"
            "[gitignore-bypass] These paths are gitignored for a reason. Do not force-add them."
        )


def check_git_submission(command: str) -> None:
    """Block raw git push, gh pr create, gh pr merge unless bypassed."""
    # Skills prefix blocked commands with CLAUDE_GATE_BYPASS=1 to pass through
    if command.lstrip().startswith(_GIT_SUBMISSION_BYPASS):
        return

    for pattern, skill_name, message in _GIT_SUBMISSION_PATTERNS:
        if pattern.search(command):
            _block(f"[git-submission-gate] BLOCKED: {message}\n[fix-with-skill] {skill_name}")


def check_dangerous_command(command: str) -> None:
    """Block destructive commands unless bypassed or whitelisted."""
    if os.environ.get(_DANGEROUS_BYPASS_ENV) == "1":
        return

    # Intentionally scans full command including heredoc bodies.
    # Over-blocking preferred for destructive commands.
    for pattern, category, description in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            whitelist = _load_guard_whitelist()
            if _is_whitelisted(command, whitelist):
                return
            _block(
                f"[dangerous-command] BLOCKED: {description} ({category})\n"
                f"[dangerous-command] Command: {command}\n"
                f"[dangerous-command] To allow: add pattern to .guard-whitelist"
            )


def check_creation_gate(file_path: str) -> None:
    """Block new agent/skill file creation unless bypassed."""
    if os.environ.get(_CREATION_BYPASS_ENV) == "1":
        return

    is_agent = bool(_AGENT_PATTERN.search(file_path))
    is_skill = bool(_SKILL_PATTERN.search(file_path))
    if not is_agent and not is_skill:
        return

    # Allow overwrites of existing files (update, not creation)
    if Path(file_path).exists():
        return

    component_type = "agent" if is_agent else "skill"
    _block(
        f"[creation-gate] BLOCKED: New {component_type} must be created via skill-creator or skill-creation-pipeline.\n"
        f"[creation-gate] Path: {file_path}\n"
        f"[fix-with-agent] skill-creator"
    )


def check_sensitive_file(file_path: str) -> None:
    """Block writes to sensitive files unless bypassed or excepted."""
    if os.environ.get(_SENSITIVE_BYPASS_ENV) == "1":
        return

    if _is_sensitive_exception(file_path):
        return

    all_patterns = _SENSITIVE_PATTERNS + _load_guard_patterns()
    for pattern, category, description in all_patterns:
        if pattern.search(file_path):
            _block(
                f"[sensitive-file-guard] BLOCKED: Write to sensitive file ({category})\n"
                f"[sensitive-file-guard] Path: {file_path}\n"
                f"[sensitive-file-guard] Pattern: {description}\n"
                f"[sensitive-file-guard] To allow: set SENSITIVE_FILE_GUARD_BYPASS=1 or add exception to .guard-patterns"
            )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    # Field name compatibility: try new names first, fall back to old
    tool = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))

    if tool == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return
        check_gitignore_bypass(command)
        check_git_submission(command)
        check_dangerous_command(command)

    elif tool == "Write":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_creation_gate(file_path)
        check_sensitive_file(file_path)

    elif tool == "Edit":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_sensitive_file(file_path)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(2) propagate for blocks
    except Exception as e:
        # Fail OPEN — a crashed hook must never exit 2.
        print(f"[unified-gate] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(0)

#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Sensitive File Guard

Blocks writes to files matching sensitive patterns: .env files, credential
files, SSH keys, certificates, cloud configs, and token files.

This is a HARD GATE — exit 2 blocks the write. Path-based matching only
(no content inspection). Complements pretool-creation-gate.py (wrong
directories) and pretool-git-submission-gate.py (git operations).

Exceptions (never block):
- .env.example (template files)
- Files in test fixture directories (testdata/, fixtures/, __fixtures__/)
- SENSITIVE_FILE_GUARD_BYPASS=1 env var

Per-project extensions: .guard-patterns (one glob per line, extends defaults).

Performance target: <5ms (path matching only, no I/O beyond whitelist read).

ADR: adr/013-sensitive-file-guard.md
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "SENSITIVE_FILE_GUARD_BYPASS"

# Compiled patterns for sensitive file paths.
# Each tuple: (compiled_regex, category, human_description)
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

# Patterns that are ALWAYS allowed (override sensitive patterns)
_EXCEPTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.sample$"),
    re.compile(r"\.env\.template$"),
    re.compile(r"/testdata/"),
    re.compile(r"/fixtures/"),
    re.compile(r"/__fixtures__/"),
    re.compile(r"/test_?data/"),
]


def _load_extra_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Load per-project sensitive patterns from .guard-patterns."""
    guard_path = Path.cwd() / ".guard-patterns"
    if not guard_path.is_file():
        return []
    extra = []
    try:
        for line in guard_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Convert glob-style to regex (simple: * -> .*, ? -> .)
                regex = line.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                extra.append((re.compile(regex), "custom", line))
    except OSError:
        pass
    return extra


def _is_exception(file_path: str) -> bool:
    """Check if file matches an exception pattern."""
    return any(p.search(file_path) for p in _EXCEPTION_PATTERNS)


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    if os.environ.get(_BYPASS_ENV) == "1":
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check exceptions first (fast path)
    if _is_exception(file_path):
        sys.exit(0)

    # Check default patterns
    all_patterns = _SENSITIVE_PATTERNS + _load_extra_patterns()
    for pattern, category, description in all_patterns:
        if pattern.search(file_path):
            print(
                f"[sensitive-file-guard] BLOCKED: Write to sensitive file ({category})\n"
                f"[sensitive-file-guard] Path: {file_path}\n"
                f"[sensitive-file-guard] Pattern: {description}\n"
                f"[sensitive-file-guard] To allow: set SENSITIVE_FILE_GUARD_BYPASS=1 or add exception to .guard-patterns",
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

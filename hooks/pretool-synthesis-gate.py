#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse:Write,Edit Hook: Consultation Synthesis Gate

Blocks feature implementation when an ADR exists but consultation
synthesis is missing or BLOCKED. Forces agents to complete consultation
before writing implementation code.

This is a HARD GATE — exit 2 blocks the Write/Edit tool.

Detection logic:
- Tool is Write or Edit
- .adr-session.json exists (active ADR session)
- Target path is NOT in hooks/, scripts/, adr/, or test files
- No synthesis.md in the ADR consultation directory

Allow-through conditions:
- No .adr-session.json (no active ADR session)
- Target file is in hooks/, scripts/, adr/, commands/ (infrastructure, not implementation)
- Target file is a test file (*_test.go, *_test.py, test_*.py, *.test.ts)
- synthesis.md exists with PROCEED verdict
- SYNTHESIS_GATE_BYPASS=1 env var (for the consultation skill itself)
"""

import json
import os
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from stdin_timeout import read_stdin

_BYPASS_ENV = "SYNTHESIS_GATE_BYPASS"

# Paths exempt from the gate — infrastructure, not implementation.
_EXEMPT_PREFIXES = (
    "/hooks/",
    "/scripts/",
    "/adr/",
    "/commands/",
    "/docs/",
    "/.claude/",
    "/.feature/",
    "/.github/",
)

# File name patterns that are never implementation code.
_EXEMPT_NAMES = (
    "task_plan.md",
    "CLAUDE.md",
    "README.md",
    "MEMORY.md",
    "HANDOFF.json",
    ".adr-session.json",
    ".gitignore",
)

# Test file patterns — always exempt.
_TEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"_test\.go$"),
    re.compile(r"_test\.py$"),
    re.compile(r"/test_[^/]+\.py$"),
    re.compile(r"\.test\.ts$"),
]


def _is_exempt(file_path: str) -> bool:
    """Return True if the target path is infrastructure or a test file."""
    # Normalise to forward-slash for cross-platform safety.
    normalised = file_path.replace("\\", "/")
    basename = normalised.rsplit("/", 1)[-1] if "/" in normalised else normalised

    # Infrastructure directories
    for prefix in _EXEMPT_PREFIXES:
        if prefix in normalised:
            return True

    # Known non-implementation files
    if basename in _EXEMPT_NAMES:
        return True

    # Test files
    for pattern in _TEST_PATTERNS:
        if pattern.search(normalised):
            return True

    return False


def _load_session(base_dir: Path) -> dict | None:
    """Load .adr-session.json from base_dir. Returns None if absent or malformed."""
    session_path = base_dir / ".adr-session.json"
    if not session_path.is_file():
        return None
    try:
        return json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _synthesis_verdict(synthesis_path: Path) -> str | None:
    """
    Return the verdict string from synthesis.md, or None if the file is missing.

    Scans for a line containing 'PROCEED' or 'BLOCKED' (case-insensitive).
    Returns 'PROCEED', 'BLOCKED', or 'UNKNOWN' if neither keyword is found.
    """
    if not synthesis_path.is_file():
        return None
    try:
        text = synthesis_path.read_text(encoding="utf-8").upper()
    except OSError:
        return None

    if "PROCEED" in text:
        return "PROCEED"
    if "BLOCKED" in text:
        return "BLOCKED"
    return "UNKNOWN"


def main() -> None:
    debug = os.environ.get("CLAUDE_HOOKS_DEBUG")

    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = event.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    # Bypass env var — set by the consultation skill itself.
    if os.environ.get(_BYPASS_ENV) == "1":
        if debug:
            print("[synthesis-gate] Bypassed via SYNTHESIS_GATE_BYPASS=1", file=sys.stderr)
        sys.exit(0)

    tool_input = event.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Exempt infrastructure and test paths — always allow.
    if _is_exempt(file_path):
        if debug:
            print(f"[synthesis-gate] Exempt path: {file_path}", file=sys.stderr)
        sys.exit(0)

    # Resolve project root: prefer event["cwd"], then CLAUDE_PROJECT_DIR, then cwd.
    cwd_str = event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR", ".")
    base_dir = Path(cwd_str).resolve()

    session = _load_session(base_dir)
    if session is None:
        # No active ADR session — gate is dormant.
        if debug:
            print("[synthesis-gate] No .adr-session.json found — allowing through", file=sys.stderr)
        sys.exit(0)

    domain = session.get("domain", "")
    adr_name = domain or Path(session.get("adr_path", "unknown")).stem

    if debug:
        print(f"[synthesis-gate] Active ADR session: domain={adr_name}", file=sys.stderr)

    # Locate synthesis.md: adr/{domain}/synthesis.md
    synthesis_path = base_dir / "adr" / adr_name / "synthesis.md"
    verdict = _synthesis_verdict(synthesis_path)

    if verdict is None:
        # synthesis.md is missing — block until consultation is run.
        print(
            f"[synthesis-gate] BLOCKED: Consultation required. "
            f"Run /adr-consultation on {adr_name} first.\n"
            f"[synthesis-gate] Expected: {synthesis_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    if verdict == "BLOCKED":
        print(
            f"[synthesis-gate] BLOCKED: Consultation verdict is BLOCKED for {adr_name}.\n"
            f"[synthesis-gate] Review {synthesis_path} and resolve concerns before implementing.",
            file=sys.stderr,
        )
        sys.exit(2)

    # PROCEED or UNKNOWN — allow through.
    if debug:
        print(f"[synthesis-gate] Verdict={verdict} for {adr_name} — allowing through", file=sys.stderr)
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
            print(f"[synthesis-gate] Error: {type(e).__name__}: {e}", file=sys.stderr)
        # A crashed hook must fail OPEN — never exit 2 on unexpected errors.
        sys.exit(0)
